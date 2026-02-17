from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.views.generic import TemplateView, CreateView, FormView, ListView, DetailView, UpdateView
from django.urls import reverse_lazy
from django.core.cache import cache
from django.core.mail import send_mail
from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse, HttpResponseForbidden, HttpResponse
from django.db import transaction, IntegrityError
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from django.utils import timezone
from django.db import models
from datetime import timedelta
import uuid
import random
import logging
import json
from datetime import date
from functools import wraps
import csv
import re
import os
import time

from .forms import (
    VoterRegistrationForm, 
    VoterLoginForm,
    DeviceResetRequestForm,
    PasswordResetRequestForm,
    PasswordResetVerifyForm,
    AdminLoginForm,
    AdminRegistrationForm,
    AdminPasswordResetRequestForm,
    AdminPasswordResetVerifyForm,
    AdminDeviceResetRequestForm,
    AccountDeletionForm,
    UserProfileForm,
    AdminApprovalForm,
    SuspendAccountForm,
    BulkActionForm
)
from .models import User, AdminProfile, AccountActionRequest, Notification, AuditLog
from .utils import (
    send_account_request_received, 
    send_account_request_approved, 
    send_account_request_rejected,
    send_admin_approval_request,
    send_account_deletion_confirmation,
    send_account_suspension_notice,
    send_account_reactivation_notice,
    send_kyc_verification_notice,
    send_tsc_verification_notice,
    send_welcome_email,
    create_notification,
    log_audit_action,
    generate_unique_admin_id,
    get_user_by_identifier
)
from apps.core.models import DeviceResetRequest as CoreDeviceResetRequest
from apps.voting.models import ElectionSettings, Candidate, Team, Position, Vote

logger = logging.getLogger(__name__)

# ==================== HELPER FUNCTIONS ====================

def get_client_ip(request):
    """Get client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR', '0.0.0.0')

def rate_limit(key='ip', rate='5/m'):
    """Custom rate limiting decorator"""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(instance, request, *args, **kwargs):
            limit, period = rate.split('/')
            limit = int(limit)
            
            if key == 'ip':
                client_id = get_client_ip(request)
            else:
                client_id = request.POST.get(key, request.GET.get(key, ''))
            
            if not client_id:
                client_id = 'unknown'
            
            if period == 'm':
                timeout = 60
            elif period == 'h':
                timeout = 3600
            elif period == 'd':
                timeout = 86400
            else:
                timeout = 60
            
            cache_key = f"rate_limit_{key}_{client_id}"
            attempts = cache.get(cache_key, 0)
            
            if attempts >= limit:
                return JsonResponse({
                    'error': f'Rate limit exceeded. Maximum {limit} requests per {period}.'
                }, status=429)
            
            cache.set(cache_key, attempts + 1, timeout)
            
            return view_func(instance, request, *args, **kwargs)
        return _wrapped_view
    return decorator

def can_request_otp(email):
    """Check if user can request OTP based on rate limit"""
    cache_key = f"otp_requests_{email}"
    requests = cache.get(cache_key, 0)
    return requests < settings.OTP_RATE_LIMIT

def increment_otp_request_count(email):
    """Increment OTP request count"""
    cache_key = f"otp_requests_{email}"
    requests = cache.get(cache_key, 0)
    cache.set(cache_key, requests + 1, settings.OTP_RATE_LIMIT_PERIOD)

def get_remaining_otp_requests(email):
    """Get remaining OTP requests for user"""
    cache_key = f"otp_requests_{email}"
    requests = cache.get(cache_key, 0)
    return max(0, settings.OTP_RATE_LIMIT - requests)

# ==================== OTP VIEWS ====================

def send_otp(request):
    """Send OTP to email for verification"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        email = data.get('email', '').lower().strip()
        
        if not email:
            return JsonResponse({'error': 'Email required'}, status=400)
        
        if not can_request_otp(email):
            remaining = get_remaining_otp_requests(email)
            return JsonResponse({
                'error': f'Too many OTP requests. {remaining} remaining today.'
            }, status=429)
        
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        cache.set(f"email_otp_{email}", otp, timeout=600)
        increment_otp_request_count(email)
        
        send_mail(
            'Verify Your Email - Agora',
            f'Your verification code is: {otp}\n\nThis code expires in 10 minutes.',
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False,
        )
        
        remaining = get_remaining_otp_requests(email)
        return JsonResponse({'success': True, 'remaining': remaining})
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"OTP send error: {e}")
        return JsonResponse({'error': 'Failed to send OTP'}, status=500)

def verify_otp(request):
    """Verify OTP for email"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        email = data.get('email', '').lower().strip()
        otp = data.get('otp', '').strip()
        
        if not email or not otp:
            return JsonResponse({'error': 'Email and OTP required'}, status=400)
        
        cached_otp = cache.get(f"email_otp_{email}")
        
        if cached_otp and cached_otp == otp:
            cache.delete(f"email_otp_{email}")
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'Invalid or expired OTP'}, status=400)
    
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        logger.error(f"OTP verify error: {e}")
        return JsonResponse({'error': 'Verification failed'}, status=500)

def get_otp_status(request):
    """Get OTP request status for user"""
    email = request.GET.get('email', '').lower().strip()
    if not email:
        return JsonResponse({'error': 'Email required'}, status=400)
    
    remaining = get_remaining_otp_requests(email)
    return JsonResponse({'remaining': remaining, 'limit': settings.OTP_RATE_LIMIT})

def save_step1_data(request):
    """Save step 1 personal data to session"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=405)
    
    try:
        data = json.loads(request.body)
        request.session['registration_step1'] = data
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Step1 save error: {e}")
        return JsonResponse({'error': 'Failed to save data'}, status=500)

def get_step1_data(request):
    """Get step 1 personal data from session"""
    data = request.session.get('registration_step1', {})
    return JsonResponse(data)

# ==================== LANDING PAGE VIEW ====================

class LandingPageView(TemplateView):
    """Landing page view"""
    template_name = 'accounts/landing.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        try:
            context['election'] = ElectionSettings.get_settings()
        except Exception as e:
            logger.error(f"Error getting election settings: {e}")
            context['election'] = None
        return context

# ==================== VOTER VIEWS ====================

@method_decorator([never_cache, csrf_protect], name='dispatch')
class VoterRegistrationView(CreateView):
    """Handle voter registration with KYC and device binding"""
    template_name = 'accounts/register.html'
    form_class = VoterRegistrationForm
    success_url = reverse_lazy('accounts:registration_complete')
    
    @rate_limit(key='ip', rate='3/m')
    def dispatch(self, request, *args, **kwargs):
        fingerprint = request.session.get('device_fingerprint')
        if fingerprint and User.objects.filter(device_fingerprint=fingerprint).exists():
            messages.error(request, "This device has already been used for registration.")
            return redirect('accounts:login')
        return super().dispatch(request, *args, **kwargs)
    
    def get_initial(self):
        initial = super().get_initial()
        step1_data = self.request.session.get('registration_step1', {})
        initial.update(step1_data)
        return initial
    
    def form_valid(self, form):
        try:
            with transaction.atomic():
                user = form.save(commit=False)
                user.device_fingerprint = self.request.session.get('device_fingerprint')
                user.ip_address = get_client_ip(self.request)
                user.user_agent = self.request.META.get('HTTP_USER_AGENT', '')
                user.vote_token = uuid.uuid4()
                user.is_active = True
                user.email_verified = True
                user.kyc_status = 'PENDING'
                user.kyc_submitted_at = timezone.now()
                user.account_status = 'PENDING'
                
                # Handle file uploads
                id_front = self.request.FILES.get('id_front')
                if id_front:
                    ext = id_front.name.split('.')[-1]
                    filename = f"{user.tsc_number}_front_{uuid.uuid4()}.{ext}"
                    file_path = default_storage.save(f'kyc/ids/{filename}', ContentFile(id_front.read()))
                    user.id_front = file_path
                    user.id_front_status = 'UPLOADED'
                
                id_back = self.request.FILES.get('id_back')
                if id_back:
                    ext = id_back.name.split('.')[-1]
                    filename = f"{user.tsc_number}_back_{uuid.uuid4()}.{ext}"
                    file_path = default_storage.save(f'kyc/ids/{filename}', ContentFile(id_back.read()))
                    user.id_back = file_path
                    user.id_back_status = 'UPLOADED'
                
                face_photo = self.request.FILES.get('face_photo')
                if face_photo:
                    ext = face_photo.name.split('.')[-1]
                    filename = f"{user.tsc_number}_face_{uuid.uuid4()}.{ext}"
                    file_path = default_storage.save(f'kyc/faces/{filename}', ContentFile(face_photo.read()))
                    user.face_photo = file_path
                    user.face_photo_status = 'UPLOADED'
                
                user.save()
                
                # Create notification
                create_notification(
                    user=user,
                    title='Registration Successful',
                    message='Your account has been created successfully. Please wait for KYC verification.',
                    notification_type='SUCCESS'
                )
                
                log_audit_action(user, 'User registered', 'USER', self.request)
                
                if 'registration_step1' in self.request.session:
                    del self.request.session['registration_step1']
                
                login(self.request, user, backend='django.contrib.auth.backends.ModelBackend')
                
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'redirect': str(self.success_url)})
                
                messages.success(self.request, "Registration successful!")
                return redirect(self.success_url)
                
        except IntegrityError as e:
            error_msg = "Registration failed. This account may already exist."
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(self.request, error_msg)
            return self.form_invalid(form)
                
        except Exception as e:
            logger.error(f"Unexpected error during registration: {e}", exc_info=True)
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': f'Registration failed'}, status=500)
            messages.error(self.request, "Registration failed. Please try again.")
            return self.form_invalid(form)
    
    def form_invalid(self, form):
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(error) for error in error_list]
            return JsonResponse({
                'error': 'Validation failed',
                'field_errors': errors
            }, status=400)
        
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

@method_decorator([never_cache, csrf_protect], name='dispatch')
class VoterLoginView(FormView):
    """Handle voter login"""
    template_name = 'accounts/login.html'
    form_class = VoterLoginForm
    success_url = reverse_lazy('core:dashboard')
    
    def dispatch(self, request, *args, **kwargs):
        client_ip = get_client_ip(request)
        cache_key = f"login_attempts_{client_ip}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= 5:
            messages.error(request, "Too many login attempts. Please try again later.")
            return self.form_invalid(self.get_form())
        
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        tsc_number = form.cleaned_data['tsc_number']
        password = form.cleaned_data['password']
        
        client_ip = get_client_ip(self.request)
        cache_key = f"login_attempts_{client_ip}"
        attempts = cache.get(cache_key, 0)
        
        user = authenticate(self.request, username=tsc_number, password=password)
        
        if user:
            cache.delete(cache_key)
            
            if user.user_type != 'VOTER':
                messages.error(self.request, "This account is not a voter account.")
                return self.form_invalid(form)
            
            if user.account_status == 'SUSPENDED':
                messages.error(self.request, "Your account has been suspended. Please contact support.")
                return self.form_invalid(form)
            
            if not user.is_active:
                messages.error(self.request, "Your account is inactive.")
                return self.form_invalid(form)
            
            current_fingerprint = self.request.session.get('device_fingerprint')
            if user.device_fingerprint and user.device_fingerprint != current_fingerprint:
                messages.error(self.request, "You can only log in from your registered device.")
                return self.form_invalid(form)
            
            user.last_login_ip = client_ip
            user.save()
            
            login(self.request, user)
            
            log_audit_action(user, 'User logged in', 'USER', self.request)
            
            messages.success(self.request, f"Welcome back, {user.full_name}!")
            return redirect(self.success_url)
        else:
            cache.set(cache_key, attempts + 1, timeout=900)
            remaining = 4 - attempts
            messages.error(self.request, f"Invalid credentials. {remaining} attempts remaining.")
            return self.form_invalid(form)

class DeviceResetRequestView(CreateView):
    """Handle device reset requests"""
    template_name = 'accounts/device_reset.html'
    form_class = DeviceResetRequestForm
    success_url = reverse_lazy('accounts:reset_request_complete')
    
    def dispatch(self, request, *args, **kwargs):
        try:
            election = ElectionSettings.get_settings()
            if election.voting_date and (election.voting_date - date.today()).days < 3:
                messages.error(request, "Device reset requests must be submitted at least 3 days before voting.")
                return redirect('landing')
        except Exception:
            pass
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        reset_request = form.save(commit=False)
        reset_request.new_device_fingerprint = self.request.session.get('device_fingerprint', '')
        reset_request.save()
        
        # Create action request
        AccountActionRequest.objects.create(
            user=reset_request.user,
            action_type='DEVICE_RESET',
            reason=reset_request.reason,
            metadata={'request_id': reset_request.id}
        )
        
        send_account_request_received(reset_request.user, 'Device Reset')
        
        messages.success(self.request, "Your device reset request has been submitted.")
        return redirect(self.success_url)

def logout_view(request):
    """Custom logout view"""
    user = request.user
    if user.is_authenticated:
        log_audit_action(user, 'User logged out', 'USER', request)
    logout(request)
    messages.info(request, "You have been logged out successfully.")
    return redirect('landing')

def check_tsc_availability(request):
    """Check if TSC number is available"""
    tsc_number = request.GET.get('tsc_number', '').strip()
    return JsonResponse({'is_taken': User.objects.filter(tsc_number=tsc_number).exists()})

def check_id_availability(request):
    """Check if ID number is available"""
    id_number = request.GET.get('id_number', '').strip()
    return JsonResponse({'is_taken': User.objects.filter(id_number=id_number).exists()})

def check_email_availability(request):
    """Check if email is available"""
    email = request.GET.get('email', '').lower().strip()
    return JsonResponse({'is_taken': User.objects.filter(email=email).exists()})

# ==================== ACCOUNT DELETION VIEWS ====================

@method_decorator([login_required], name='dispatch')
class DeleteAccountRequestView(FormView):
    """View for users to request account deletion"""
    template_name = 'accounts/delete_account.html'
    form_class = AccountDeletionForm
    success_url = reverse_lazy('core:dashboard')
    
    def form_valid(self, form):
        user = self.request.user
        reason = form.cleaned_data['reason']
        
        # Create deletion request
        action_request = AccountActionRequest.objects.create(
            user=user,
            action_type='DELETE',
            reason=reason,
            metadata={'requested_by_user': True}
        )
        
        # Update user
        user.deletion_requested = True
        user.deletion_requested_at = timezone.now()
        user.deletion_reason = reason
        user.save()
        
        # Create notification
        create_notification(
            user=user,
            title='Deletion Request Received',
            message='Your account deletion request has been submitted and is pending review.',
            notification_type='INFO'
        )
        
        # Send email
        send_account_request_received(user, 'Account Deletion')
        
        # Log audit
        log_audit_action(user, 'Account deletion requested', 'USER', self.request, {'reason': reason})
        
        messages.success(self.request, "Your account deletion request has been submitted. You will receive an email once processed.")
        return redirect(self.success_url)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        return context

@method_decorator([login_required], name='dispatch')
class CancelDeletionRequestView(TemplateView):
    """View for users to cancel their deletion request"""
    
    def post(self, request, *args, **kwargs):
        user = request.user
        
        if user.deletion_requested:
            user.deletion_requested = False
            user.deletion_requested_at = None
            user.deletion_reason = ''
            user.save()
            
            # Update action request
            AccountActionRequest.objects.filter(
                user=user,
                action_type='DELETE',
                status='PENDING'
            ).update(status='CANCELLED')
            
            create_notification(
                user=user,
                title='Deletion Request Cancelled',
                message='Your account deletion request has been cancelled.',
                notification_type='INFO'
            )
            
            log_audit_action(user, 'Deletion request cancelled', 'USER', request)
            
            messages.success(request, "Your deletion request has been cancelled.")
        
        return redirect('core:dashboard')

# ==================== PASSWORD RESET VIEWS ====================

class PasswordResetRequestView(FormView):
    """Request password reset with email OTP"""
    template_name = 'accounts/password_reset_request.html'
    form_class = PasswordResetRequestForm
    success_url = reverse_lazy('accounts:password_reset_verify')
    
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        email = form.cleaned_data['email'].lower().strip()
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(self.request, "No account found with this email address.")
            return self.form_invalid(form)
        
        client_ip = get_client_ip(self.request)
        ip_cache_key = f"password_reset_ip_{client_ip}"
        ip_attempts = cache.get(ip_cache_key, 0)
        
        if ip_attempts >= 3:
            messages.error(self.request, "Too many password reset attempts. Please try again later.")
            return self.form_invalid(form)
        
        if not can_request_otp(email):
            remaining = get_remaining_otp_requests(email)
            messages.error(self.request, f"Too many OTP requests. You have {remaining} requests remaining today.")
            return self.form_invalid(form)
        
        cache.set(ip_cache_key, ip_attempts + 1, timeout=3600)
        
        otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
        cache.set(f"password_reset_{email}", otp, timeout=600)
        increment_otp_request_count(email)
        
        try:
            send_mail(
                'Password Reset OTP - Agora',
                f'Your OTP for password reset is: {otp}\n\nThis code expires in 10 minutes.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            remaining = get_remaining_otp_requests(email)
            messages.success(self.request, f"OTP sent to your email. You have {remaining} requests remaining today.")
            self.request.session['reset_email'] = email
            return super().form_valid(form)
            
        except Exception as e:
            logger.error(f"Failed to send password reset email to {email}: {e}")
            messages.error(self.request, "Failed to send OTP. Please try again later.")
            return self.form_invalid(form)

class PasswordResetVerifyView(FormView):
    """Verify OTP and reset password"""
    template_name = 'accounts/password_reset_verify.html'
    form_class = PasswordResetVerifyForm
    success_url = reverse_lazy('accounts:login')
    
    def form_valid(self, form):
        otp = form.cleaned_data['otp'].strip()
        email = self.request.session.get('reset_email')
        
        if not email:
            messages.error(self.request, "Session expired. Please start over.")
            return redirect('accounts:password_reset_request')
        
        cached_otp = cache.get(f"password_reset_{email}")
        
        if cached_otp and cached_otp == otp:
            password = form.cleaned_data['new_password1']
            
            try:
                user = User.objects.get(email=email)
                user.set_password(password)
                user.save()
                
                # Create notification
                create_notification(
                    user=user,
                    title='Password Reset Successful',
                    message='Your password has been reset successfully.',
                    notification_type='SUCCESS'
                )
                
                cache.delete(f"password_reset_{email}")
                del self.request.session['reset_email']
                
                log_audit_action(user, 'Password reset', 'SECURITY', self.request)
                
                messages.success(self.request, "Password reset successful. Please login with your new password.")
                return super().form_valid(form)
                
            except User.DoesNotExist:
                messages.error(self.request, "User account not found.")
                return redirect('accounts:password_reset_request')
            except Exception as e:
                logger.error(f"Password reset error for {email}: {e}")
                messages.error(self.request, "An error occurred. Please try again.")
                return self.form_invalid(form)
        else:
            messages.error(self.request, "Invalid or expired OTP.")
            return self.form_invalid(form)

# ==================== NOTIFICATION VIEWS ====================

@method_decorator([login_required], name='dispatch')
class NotificationListView(ListView):
    """List user notifications"""
    template_name = 'accounts/notifications.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unread_count'] = Notification.objects.filter(
            user=self.request.user, is_read=False
        ).count()
        return context

@method_decorator([login_required], name='dispatch')
class MarkNotificationReadView(TemplateView):
    """Mark a notification as read"""
    
    def post(self, request, *args, **kwargs):
        notification_id = kwargs.get('pk')
        try:
            notification = Notification.objects.get(id=notification_id, user=request.user)
            notification.mark_as_read()
            return JsonResponse({'success': True})
        except Notification.DoesNotExist:
            return JsonResponse({'error': 'Notification not found'}, status=404)

@method_decorator([login_required], name='dispatch')
class MarkAllNotificationsReadView(TemplateView):
    """Mark all notifications as read"""
    
    def post(self, request, *args, **kwargs):
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True,
            read_at=timezone.now()
        )
        return JsonResponse({'success': True})

# ==================== ADMIN VIEWS ====================

class AdminLoginView(FormView):
    """Admin login view - redirects to admin dashboard on success"""
    template_name = 'admin_panel/admin_login.html'
    form_class = AdminLoginForm
    success_url = reverse_lazy('admin_panel:dashboard')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.user.user_type in ['ADMIN', 'SUPER_ADMIN']:
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        username = form.cleaned_data['username']
        password = form.cleaned_data['password']
        
        user = authenticate(self.request, username=username, password=password)
        
        if user is not None and user.user_type in ['ADMIN', 'SUPER_ADMIN']:
            if user.account_status == 'SUSPENDED':
                messages.error(self.request, "Your admin account has been suspended.")
                return self.form_invalid(form)
            
            login(self.request, user)
            
            log_audit_action(user, 'Admin logged in', 'ADMIN', self.request)
            
            messages.success(self.request, f"Welcome back, {user.full_name}!")
            return redirect(self.success_url)
        else:
            messages.error(self.request, "Invalid credentials or insufficient permissions")
            return self.form_invalid(form)

class AdminRegistrationView(CreateView):
    """Admin registration view with approval workflow"""
    template_name = 'admin_panel/admin_register.html'
    form_class = AdminRegistrationForm
    success_url = reverse_lazy('accounts:admin_login')
    
    def dispatch(self, request, *args, **kwargs):
        logger.info("=" * 50)
        logger.info("ADMIN REGISTRATION ATTEMPT STARTED")
        logger.info(f"Request Method: {request.method}")
        logger.info(f"IP Address: {get_client_ip(request)}")
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['counties'] = self.get_county_choices()
        return context
    
    def get_county_choices(self):
        return [
            'Mombasa', 'Kwale', 'Kilifi', 'Tana River', 'Lamu', 'Taita Taveta',
            'Garissa', 'Wajir', 'Mandera', 'Marsabit', 'Isiolo', 'Meru',
            'Tharaka Nithi', 'Embu', 'Kitui', 'Machakos', 'Makueni', 'Nyandarua',
            'Nyeri', 'Kirinyaga', "Murang'a", 'Kiambu', 'Turkana', 'West Pokot',
            'Samburu', 'Trans Nzoia', 'Uasin Gishu', 'Elgeyo Marakwet', 'Nandi',
            'Baringo', 'Laikipia', 'Nakuru', 'Narok', 'Kajiado', 'Kericho',
            'Bomet', 'Kakamega', 'Vihiga', 'Bungoma', 'Busia', 'Siaya', 'Kisumu',
            'Homa Bay', 'Migori', 'Kisii', 'Nyamira', 'Nairobi'
        ]
    
    def form_valid(self, form):
        logger.info("=" * 50)
        logger.info("ADMIN REGISTRATION FORM VALID")
        
        # Check terms agreement from POST data
        terms_agreed = self.request.POST.get('terms_agreed')
        logger.info(f"Terms agreed: {terms_agreed}")
        
        if not terms_agreed or terms_agreed.lower() not in ['true', 'on', '1']:
            logger.error("Terms not agreed - registration rejected")
            messages.error(self.request, "You must agree to the terms and conditions")
            return self.form_invalid(form)
        
        try:
            with transaction.atomic():
                logger.info("Starting database transaction")
                
                user = form.save(commit=False)
                logger.info(f"User object created: {user}")
                
                # Set device info
                user.device_fingerprint = self.request.session.get('device_fingerprint')
                user.ip_address = get_client_ip(self.request)
                user.user_agent = self.request.META.get('HTTP_USER_AGENT', '')
                user.is_active = False  # Admin accounts need approval
                user.email_verified = True
                user.account_status = 'PENDING'
                
                logger.info(f"Device fingerprint: {user.device_fingerprint}")
                logger.info(f"IP Address: {user.ip_address}")
                
                # Handle file uploads
                id_front = self.request.FILES.get('id_front')
                if id_front:
                    logger.info(f"Processing ID front: {id_front.name}, size: {id_front.size}")
                    # Validate file type
                    if not id_front.content_type.startswith('image/'):
                        messages.error(self.request, "ID front must be an image file")
                        return self.form_invalid(form)
                    
                    # Save file
                    ext = os.path.splitext(id_front.name)[1]
                    filename = f"admin_{int(time.time())}_front{ext}"
                    file_path = default_storage.save(f'admin/ids/{filename}', ContentFile(id_front.read()))
                    user.id_front = file_path
                    logger.info(f"ID front saved: {file_path}")
                
                id_back = self.request.FILES.get('id_back')
                if id_back:
                    logger.info(f"Processing ID back: {id_back.name}, size: {id_back.size}")
                    if not id_back.content_type.startswith('image/'):
                        messages.error(self.request, "ID back must be an image file")
                        return self.form_invalid(form)
                    
                    ext = os.path.splitext(id_back.name)[1]
                    filename = f"admin_{int(time.time())}_back{ext}"
                    file_path = default_storage.save(f'admin/ids/{filename}', ContentFile(id_back.read()))
                    user.id_back = file_path
                    logger.info(f"ID back saved: {file_path}")
                
                selfie_photo = self.request.FILES.get('selfie_photo')
                if selfie_photo:
                    logger.info(f"Processing selfie photo: {selfie_photo.name}, size: {selfie_photo.size}")
                    if not selfie_photo.content_type.startswith('image/'):
                        messages.error(self.request, "Selfie photo must be an image file")
                        return self.form_invalid(form)
                    
                    ext = os.path.splitext(selfie_photo.name)[1]
                    filename = f"admin_{int(time.time())}_selfie{ext}"
                    file_path = default_storage.save(f'admin/faces/{filename}', ContentFile(selfie_photo.read()))
                    user.face_photo = file_path
                    logger.info(f"Selfie photo saved: {file_path}")
                
                logger.info("Attempting to save user to database...")
                user.save()
                logger.info(f"User saved successfully with ID: {user.id}")
                
                # Create AdminProfile
                from .models import AdminProfile
                logger.info("Creating AdminProfile...")
                admin_profile = AdminProfile.objects.create(
                    user=user,
                    national_id=form.cleaned_data['id_number'],
                    county_of_residence=form.cleaned_data['county'],
                    id_document=id_front,
                    selfie_photo=selfie_photo,
                    is_verified=False
                )
                logger.info(f"AdminProfile created: {admin_profile}")
                
                # Send email notification to super admins
                self.notify_super_admins(user)
                
                logger.info(f"Admin registration successful: {user.email}")
                
                if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return JsonResponse({'success': True, 'redirect': str(self.success_url)})
                
                messages.success(
                    self.request, 
                    "Registration successful! Your admin account is pending approval. You will be notified via email once approved."
                )
                logger.info("Redirecting to admin login")
                return redirect(self.success_url)
                
        except IntegrityError as e:
            logger.error(f"IntegrityError during admin registration: {e}")
            error_msg = "Registration failed. "
            if 'email' in str(e):
                error_msg = "This email address is already registered."
            elif 'id_number' in str(e):
                error_msg = "This ID number is already registered."
            else:
                error_msg = "An account with this information already exists."
            
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': error_msg}, status=400)
            messages.error(self.request, error_msg)
            return self.form_invalid(form)
                
        except Exception as e:
            logger.error(f"Unexpected error during admin registration: {e}", exc_info=True)
            if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': 'Registration failed. Please try again.'}, status=500)
            messages.error(self.request, "Registration failed. Please try again.")
            return self.form_invalid(form)
        finally:
            logger.info("ADMIN REGISTRATION ATTEMPT COMPLETED")
            logger.info("=" * 50)
    
    def notify_super_admins(self, new_admin):
        """Send notification to all super admins about new registration"""
        from .models import Notification
        super_admins = User.objects.filter(user_type='SUPER_ADMIN', is_active=True)
        
        for admin in super_admins:
            try:
                Notification.objects.create(
                    user=admin,
                    title='New Admin Registration Pending Approval',
                    message=f'{new_admin.full_name} has registered as an administrator and requires approval.',
                    notification_type='ACTION_REQUIRED',
                    action_url='/admin-panel/admins/pending/'
                )
                logger.info(f"Notification sent to super admin: {admin.email}")
            except Exception as e:
                logger.error(f"Failed to notify super admin {admin.email}: {e}")
    
    def form_invalid(self, form):
        logger.warning("=" * 50)
        logger.warning("ADMIN REGISTRATION FORM INVALID")
        logger.warning(f"Form errors: {form.errors}")
        logger.warning(f"Form data: {form.data}")
        logger.warning("=" * 50)
        
        if self.request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            errors = {}
            for field, error_list in form.errors.items():
                errors[field] = [str(error) for error in error_list]
            return JsonResponse({
                'error': 'Validation failed',
                'field_errors': errors
            }, status=400)
        
        # Add error messages to messages framework
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(self.request, f"{field}: {error}")
        
        return super().form_invalid(form)
class AdminPasswordResetRequestView(FormView):
    """Admin password reset request"""
    template_name = 'admin_panel/admin_password_reset_request.html'
    form_class = AdminPasswordResetRequestForm
    success_url = reverse_lazy('accounts:admin_password_reset_verify')
    
    def form_valid(self, form):
        email = form.cleaned_data['email'].lower().strip()
        
        try:
            user = User.objects.get(email=email, user_type__in=['ADMIN', 'SUPER_ADMIN'])
            
            if not can_request_otp(email):
                remaining = get_remaining_otp_requests(email)
                messages.error(self.request, f"Too many OTP requests. You have {remaining} requests remaining today.")
                return self.form_invalid(form)
            
            otp = ''.join([str(random.randint(0, 9)) for _ in range(6)])
            cache.set(f"admin_password_reset_{email}", otp, timeout=600)
            increment_otp_request_count(email)
            
            send_mail(
                'Admin Password Reset - Agora',
                f'Your OTP for admin password reset is: {otp}\n\nThis code expires in 10 minutes.',
                settings.DEFAULT_FROM_EMAIL,
                [email],
                fail_silently=False,
            )
            
            remaining = get_remaining_otp_requests(email)
            messages.success(self.request, f"OTP sent to your email. You have {remaining} requests remaining today.")
            self.request.session['admin_reset_email'] = email
            return super().form_valid(form)
            
        except User.DoesNotExist:
            messages.error(self.request, "No admin account found with this email address.")
            return self.form_invalid(form)
        except Exception as e:
            logger.error(f"Unexpected error in password reset request: {e}", exc_info=True)
            messages.error(self.request, "An error occurred. Please try again later.")
            return self.form_invalid(form)

class AdminPasswordResetVerifyView(FormView):
    """Admin password reset verify"""
    template_name = 'admin_panel/admin_password_reset_verify.html'
    form_class = AdminPasswordResetVerifyForm
    success_url = reverse_lazy('accounts:admin_login')
    
    def form_valid(self, form):
        otp = form.cleaned_data['otp'].strip()
        email = self.request.session.get('admin_reset_email')
        
        if not email:
            messages.error(self.request, "Session expired. Please start over.")
            return redirect('accounts:admin_password_reset_request')
        
        cached_otp = cache.get(f"admin_password_reset_{email}")
        
        if cached_otp and cached_otp == otp:
            password = form.cleaned_data['new_password1']
            
            try:
                user = User.objects.get(email=email, user_type__in=['ADMIN', 'SUPER_ADMIN'])
                user.set_password(password)
                user.save()
                
                # Create notification
                create_notification(
                    user=user,
                    title='Password Reset Successful',
                    message='Your admin password has been reset successfully.',
                    notification_type='SUCCESS'
                )
                
                cache.delete(f"admin_password_reset_{email}")
                del self.request.session['admin_reset_email']
                
                log_audit_action(user, 'Admin password reset', 'ADMIN', self.request)
                
                messages.success(self.request, "Password reset successful. Please login with your new password.")
                return super().form_valid(form)
                
            except User.DoesNotExist:
                messages.error(self.request, "Admin user not found.")
                return redirect('accounts:admin_password_reset_request')
            except Exception as e:
                logger.error(f"Error resetting password: {e}", exc_info=True)
                messages.error(self.request, "An error occurred. Please try again.")
                return self.form_invalid(form)
        else:
            messages.error(self.request, "Invalid or expired OTP.")
            return self.form_invalid(form)

class AdminDeviceResetRequestView(CreateView):
    """Admin device reset request"""
    template_name = 'admin_panel/admin_device_reset.html'
    form_class = AdminDeviceResetRequestForm
    success_url = reverse_lazy('accounts:admin_reset_request_complete')
    
    def form_valid(self, form):
        try:
            reset_request = form.save(commit=False)
            reset_request.new_device_fingerprint = self.request.session.get('device_fingerprint', '')
            reset_request.save()
            
            # Create action request
            AccountActionRequest.objects.create(
                user=reset_request.user,
                action_type='DEVICE_RESET',
                reason=reset_request.reason,
                metadata={'request_id': reset_request.id}
            )
            
            send_account_request_received(reset_request.user, 'Admin Device Reset')
            
            messages.success(
                self.request, 
                "Your admin device reset request has been submitted. You will be notified once reviewed."
            )
            return redirect(self.success_url)
            
        except Exception as e:
            logger.error(f"Error saving device reset request: {e}", exc_info=True)
            messages.error(self.request, "Failed to submit request. Please try again.")
            return self.form_invalid(form)

# ==================== PROFILE VIEWS ====================

@method_decorator([login_required], name='dispatch')
class ProfileView(TemplateView):
    """User profile view"""
    template_name = 'accounts/profile.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        context['notifications'] = Notification.objects.filter(
            user=self.request.user
        )[:5]
        return context

@method_decorator([login_required], name='dispatch')
class EditProfileView(UpdateView):
    """Edit user profile"""
    model = User
    template_name = 'accounts/edit_profile.html'
    form_class = UserProfileForm
    success_url = reverse_lazy('accounts:profile')
    
    def get_object(self, queryset=None):
        return self.request.user
    
    def form_valid(self, form):
        messages.success(self.request, "Profile updated successfully.")
        log_audit_action(self.request.user, 'Profile updated', 'USER', self.request)
        return super().form_valid(form)

# ==================== ADMIN MANAGEMENT VIEWS (SUPERUSER ONLY) ====================

@method_decorator([login_required], name='dispatch')
class PendingAdminApprovalsView(ListView):
    """View for superusers to see pending admin approvals"""
    template_name = 'admin_panel/pending_admins.html'
    context_object_name = 'pending_admins'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.filter(
            user_type='ADMIN',
            account_status='PENDING',
            is_active=False
        ).order_by('-registered_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_pending'] = self.get_queryset().count()
        return context

@login_required
def approve_admin(request, admin_id):
    """Approve an admin registration"""
    if request.user.user_type != 'SUPER_ADMIN':
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        admin_user = User.objects.get(id=admin_id, user_type='ADMIN', account_status='PENDING')
    except User.DoesNotExist:
        messages.error(request, "Admin user not found.")
        return redirect('accounts:pending_admin_approvals')
    
    if request.method == 'POST':
        admin_id_number = request.POST.get('admin_id_number', '')
        
        if not admin_id_number:
            messages.error(request, "Please assign an admin ID.")
            return redirect('accounts:pending_admin_approvals')
        
        # Check if admin ID is unique
        if User.objects.filter(admin_id=admin_id_number).exists():
            messages.error(request, "This admin ID is already in use. Please choose another.")
            return redirect('accounts:pending_admin_approvals')
        
        with transaction.atomic():
            admin_user.admin_id = admin_id_number
            admin_user.is_active = True
            admin_user.account_status = 'ACTIVE'
            admin_user.verified_at = timezone.now()
            admin_user.verified_by = request.user
            admin_user.save()
            
            # Update AdminProfile
            try:
                admin_profile = AdminProfile.objects.get(user=admin_user)
                admin_profile.is_verified = True
                admin_profile.verified_at = timezone.now()
                admin_profile.verified_by = request.user
                admin_profile.save()
            except AdminProfile.DoesNotExist:
                pass
            
            # Update action request
            AccountActionRequest.objects.filter(
                user=admin_user,
                action_type='ADMIN_APPROVAL'
            ).update(
                status='APPROVED',
                processed_by=request.user,
                processed_at=timezone.now()
            )
            
            # Create notification for admin
            create_notification(
                user=admin_user,
                title='Admin Account Approved',
                message=f'Your admin account has been approved. Your Admin ID is: {admin_id_number}',
                notification_type='SUCCESS',
                action_url='/admin-panel/',
                action_text='Go to Admin Panel'
            )
            
            # Send email
            send_account_request_approved(
                admin_user, 
                'Admin Registration',
                login_url=request.build_absolute_uri('/admin-panel/')
            )
            
            log_audit_action(
                request.user, 
                f'Approved admin: {admin_user.full_name}', 
                'ADMIN', 
                request,
                {'admin_id': admin_id_number}
            )
            
            messages.success(request, f"Admin account for {admin_user.full_name} has been approved.")
        
        return redirect('accounts:pending_admin_approvals')
    
    return redirect('accounts:pending_admin_approvals')

@login_required
def reject_admin(request, admin_id):
    """Reject an admin registration"""
    if request.user.user_type != 'SUPER_ADMIN':
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        admin_user = User.objects.get(id=admin_id, user_type='ADMIN', account_status='PENDING')
    except User.DoesNotExist:
        messages.error(request, "Admin user not found.")
        return redirect('accounts:pending_admin_approvals')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'No reason provided')
        
        with transaction.atomic():
            admin_user.account_status = 'REJECTED'
            admin_user.is_active = False
            admin_user.save()
            
            # Update action request
            AccountActionRequest.objects.filter(
                user=admin_user,
                action_type='ADMIN_APPROVAL'
            ).update(
                status='REJECTED',
                processed_by=request.user,
                processed_at=timezone.now()
            )
            
            # Create notification
            create_notification(
                user=admin_user,
                title='Admin Registration Rejected',
                message=f'Your admin registration could not be approved. Reason: {reason}',
                notification_type='WARNING'
            )
            
            # Send email
            send_account_request_rejected(admin_user, 'Admin Registration', reason)
            
            log_audit_action(
                request.user, 
                f'Rejected admin: {admin_user.full_name}', 
                'ADMIN', 
                request,
                {'reason': reason}
            )
            
            messages.warning(request, f"Admin registration for {admin_user.full_name} has been rejected.")
        
        return redirect('accounts:pending_admin_approvals')
    
    return redirect('accounts:pending_admin_approvals')

@login_required
def assign_admin_id(request, admin_id):
    """Assign or change an admin ID"""
    if request.user.user_type != 'SUPER_ADMIN':
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        admin_user = User.objects.get(id=admin_id, user_type='ADMIN')
    except User.DoesNotExist:
        messages.error(request, "Admin user not found.")
        return redirect('accounts:admin_list')
    
    if request.method == 'POST':
        admin_id_number = request.POST.get('admin_id_number', '')
        
        if not admin_id_number:
            messages.error(request, "Please provide an admin ID.")
            return redirect('accounts:admin_detail', admin_id=admin_id)
        
        if User.objects.filter(admin_id=admin_id_number).exclude(id=admin_id).exists():
            messages.error(request, "This admin ID is already in use.")
            return redirect('accounts:admin_detail', admin_id=admin_id)
        
        old_admin_id = admin_user.admin_id
        admin_user.admin_id = admin_id_number
        admin_user.save()
        
        create_notification(
            user=admin_user,
            title='Admin ID Updated',
            message=f'Your admin ID has been updated to: {admin_id_number}',
            notification_type='INFO'
        )
        
        log_audit_action(
            request.user, 
            f'Updated admin ID for {admin_user.full_name}', 
            'ADMIN', 
            request,
            {'old_id': old_admin_id, 'new_id': admin_id_number}
        )
        
        messages.success(request, f"Admin ID for {admin_user.full_name} has been updated.")
        
        return redirect('accounts:admin_detail', admin_id=admin_id)
    
    return redirect('accounts:admin_detail', admin_id=admin_id)

@method_decorator([login_required], name='dispatch')
class AdminListView(ListView):
    """List all admin accounts"""
    template_name = 'admin_panel/admin_list.html'
    context_object_name = 'admins'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = User.objects.filter(user_type__in=['ADMIN', 'SUPER_ADMIN']).order_by('-registered_at')
        
        # Filter by status
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(account_status=status)
        
        # Search
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(full_name__icontains=search) |
                models.Q(email__icontains=search) |
                models.Q(admin_id__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_admins'] = User.objects.filter(user_type__in=['ADMIN', 'SUPER_ADMIN']).count()
        context['active_admins'] = User.objects.filter(user_type__in=['ADMIN', 'SUPER_ADMIN'], account_status='ACTIVE').count()
        context['suspended_admins'] = User.objects.filter(user_type__in=['ADMIN', 'SUPER_ADMIN'], account_status='SUSPENDED').count()
        context['status_filter'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('search', '')
        return context

@method_decorator([login_required], name='dispatch')
class AdminDetailView(DetailView):
    """View admin details"""
    model = User
    template_name = 'admin_panel/admin_detail.html'
    context_object_name = 'admin_user'
    pk_url_kwarg = 'admin_id'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.filter(user_type__in=['ADMIN', 'SUPER_ADMIN'])
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        admin_user = self.get_object()
        
        # Get admin profile
        try:
            context['admin_profile'] = AdminProfile.objects.get(user=admin_user)
        except AdminProfile.DoesNotExist:
            context['admin_profile'] = None
        
        # Get action history
        context['action_history'] = AccountActionRequest.objects.filter(
            user=admin_user
        ).order_by('-requested_at')[:10]
        
        # Get audit logs
        context['audit_logs'] = AuditLog.objects.filter(
            user=admin_user
        ).order_by('-timestamp')[:10]
        
        return context

@login_required
def suspend_admin(request, admin_id):
    """Suspend an admin account"""
    if request.user.user_type != 'SUPER_ADMIN':
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        admin_user = User.objects.get(id=admin_id, user_type__in=['ADMIN', 'SUPER_ADMIN'])
    except User.DoesNotExist:
        messages.error(request, "Admin user not found.")
        return redirect('accounts:admin_list')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'No reason provided')
        
        admin_user.account_status = 'SUSPENDED'
        admin_user.suspended_at = timezone.now()
        admin_user.suspended_by = request.user
        admin_user.suspension_reason = reason
        admin_user.save()
        
        # Create action request
        AccountActionRequest.objects.create(
            user=admin_user,
            action_type='SUSPEND',
            reason=reason,
            processed_by=request.user,
            processed_at=timezone.now(),
            status='COMPLETED'
        )
        
        # Create notification
        create_notification(
            user=admin_user,
            title='Account Suspended',
            message=f'Your admin account has been suspended. Reason: {reason}',
            notification_type='WARNING',
            priority='HIGH'
        )
        
        # Send email
        send_account_suspension_notice(admin_user, reason)
        
        log_audit_action(
            request.user, 
            f'Suspended admin: {admin_user.full_name}', 
            'ADMIN', 
            request,
            {'reason': reason}
        )
        
        messages.warning(request, f"Admin account for {admin_user.full_name} has been suspended.")
        
        return redirect('accounts:admin_detail', admin_id=admin_id)
    
    return redirect('accounts:admin_detail', admin_id=admin_id)

@login_required
def activate_admin(request, admin_id):
    """Activate a suspended admin account"""
    if request.user.user_type != 'SUPER_ADMIN':
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        admin_user = User.objects.get(id=admin_id, user_type__in=['ADMIN', 'SUPER_ADMIN'])
    except User.DoesNotExist:
        messages.error(request, "Admin user not found.")
        return redirect('accounts:admin_list')
    
    admin_user.account_status = 'ACTIVE'
    admin_user.suspended_at = None
    admin_user.suspended_by = None
    admin_user.suspension_reason = ''
    admin_user.save()
    
    # Create action request
    AccountActionRequest.objects.create(
        user=admin_user,
        action_type='REACTIVATE',
        processed_by=request.user,
        processed_at=timezone.now(),
        status='COMPLETED'
    )
    
    # Create notification
    create_notification(
        user=admin_user,
        title='Account Reactivated',
        message='Your admin account has been reactivated.',
        notification_type='SUCCESS'
    )
    
    # Send email
    send_account_reactivation_notice(admin_user)
    
    log_audit_action(
        request.user, 
        f'Activated admin: {admin_user.full_name}', 
        'ADMIN', 
        request
    )
    
    messages.success(request, f"Admin account for {admin_user.full_name} has been activated.")
    
    return redirect('accounts:admin_detail', admin_id=admin_id)

@login_required
def delete_admin(request, admin_id):
    """Delete an admin account"""
    if request.user.user_type != 'SUPER_ADMIN':
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        admin_user = User.objects.get(id=admin_id, user_type='ADMIN')
    except User.DoesNotExist:
        messages.error(request, "Admin user not found.")
        return redirect('accounts:admin_list')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'No reason provided')
        
        # Log before deletion
        log_audit_action(
            request.user, 
            f'Deleted admin: {admin_user.full_name}', 
            'ADMIN', 
            request,
            {'reason': reason}
        )
        
        # Delete the admin
        admin_user.delete()
        
        messages.success(request, f"Admin account for has been deleted.")
        
        return redirect('accounts:admin_list')
    
    return render(request, 'admin_panel/confirm_delete_admin.html', {'admin_user': admin_user})

@login_required
def edit_admin_permissions(request, admin_id):
    """Edit admin permissions"""
    if request.user.user_type != 'SUPER_ADMIN':
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        admin_user = User.objects.get(id=admin_id, user_type='ADMIN')
    except User.DoesNotExist:
        messages.error(request, "Admin user not found.")
        return redirect('accounts:admin_list')
    
    if request.method == 'POST':
        # Update permissions here - you can add specific permission fields
        # For now, just log the action
        log_audit_action(
            request.user, 
            f'Updated permissions for admin: {admin_user.full_name}', 
            'ADMIN', 
            request
        )
        
        messages.success(request, f"Permissions for {admin_user.full_name} have been updated.")
        
        return redirect('accounts:admin_detail', admin_id=admin_id)
    
    return render(request, 'admin_panel/edit_admin_permissions.html', {'admin_user': admin_user})

# ==================== VOTER MANAGEMENT VIEWS ====================

@method_decorator([login_required], name='dispatch')
class SuspendedVotersView(ListView):
    """List suspended voter accounts"""
    template_name = 'admin_panel/suspended_voters.html'
    context_object_name = 'suspended_voters'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.can_suspend_accounts():
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.filter(
            user_type='VOTER',
            account_status='SUSPENDED'
        ).order_by('-suspended_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_suspended'] = self.get_queryset().count()
        return context

@method_decorator([login_required], name='dispatch')
class DeletionRequestsView(ListView):
    """List account deletion requests"""
    template_name = 'admin_panel/deletion_requests.html'
    context_object_name = 'deletion_requests'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.can_delete_accounts():
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return AccountActionRequest.objects.filter(
            action_type='DELETE',
            status='PENDING'
        ).select_related('user').order_by('-requested_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_pending'] = self.get_queryset().count()
        return context

@login_required
def suspend_voter(request, voter_id):
    """Suspend a voter account"""
    if not request.user.can_suspend_accounts():
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        voter = User.objects.get(id=voter_id, user_type='VOTER')
    except User.DoesNotExist:
        messages.error(request, "Voter not found.")
        return redirect('admin_panel:voter_list')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'No reason provided')
        
        voter.account_status = 'SUSPENDED'
        voter.suspended_at = timezone.now()
        voter.suspended_by = request.user
        voter.suspension_reason = reason
        voter.save()
        
        # Create action request
        AccountActionRequest.objects.create(
            user=voter,
            action_type='SUSPEND',
            reason=reason,
            processed_by=request.user,
            processed_at=timezone.now(),
            status='COMPLETED'
        )
        
        # Create notification
        create_notification(
            user=voter,
            title='Account Suspended',
            message=f'Your account has been suspended. Reason: {reason}',
            notification_type='WARNING',
            priority='HIGH'
        )
        
        # Send email
        send_account_suspension_notice(voter, reason)
        
        log_audit_action(
            request.user, 
            f'Suspended voter: {voter.full_name}', 
            'USER', 
            request,
            {'reason': reason}
        )
        
        messages.warning(request, f"Voter account for {voter.full_name} has been suspended.")
        
        return redirect('admin_panel:voter_detail', voter_id=voter_id)
    
    return redirect('admin_panel:voter_detail', voter_id=voter_id)

@login_required
def activate_voter(request, voter_id):
    """Activate a suspended voter account"""
    if not request.user.can_suspend_accounts():
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        voter = User.objects.get(id=voter_id, user_type='VOTER')
    except User.DoesNotExist:
        messages.error(request, "Voter not found.")
        return redirect('admin_panel:voter_list')
    
    voter.account_status = 'ACTIVE'
    voter.suspended_at = None
    voter.suspended_by = None
    voter.suspension_reason = ''
    voter.save()
    
    # Create action request
    AccountActionRequest.objects.create(
        user=voter,
        action_type='REACTIVATE',
        processed_by=request.user,
        processed_at=timezone.now(),
        status='COMPLETED'
    )
    
    # Create notification
    create_notification(
        user=voter,
        title='Account Reactivated',
        message='Your account has been reactivated.',
        notification_type='SUCCESS'
    )
    
    # Send email
    send_account_reactivation_notice(voter)
    
    log_audit_action(
        request.user, 
        f'Activated voter: {voter.full_name}', 
        'USER', 
        request
    )
    
    messages.success(request, f"Voter account for {voter.full_name} has been activated.")
    
    return redirect('admin_panel:voter_detail', voter_id=voter_id)

@login_required
def delete_voter(request, voter_id):
    """Delete a voter account"""
    if not request.user.can_delete_accounts():
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        voter = User.objects.get(id=voter_id, user_type='VOTER')
    except User.DoesNotExist:
        messages.error(request, "Voter not found.")
        return redirect('admin_panel:voter_list')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'No reason provided')
        
        # Log before deletion
        log_audit_action(
            request.user, 
            f'Deleted voter: {voter.full_name}', 
            'USER', 
            request,
            {'reason': reason}
        )
        
        # Delete the voter
        voter.delete()
        
        messages.success(request, f"Voter account has been deleted.")
        
        return redirect('admin_panel:voter_list')
    
    return render(request, 'admin_panel/confirm_delete_voter.html', {'voter': voter})

@login_required
def approve_deletion(request, voter_id):
    """Approve a voter's account deletion request"""
    if not request.user.can_delete_accounts():
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        voter = User.objects.get(id=voter_id, user_type='VOTER', deletion_requested=True)
    except User.DoesNotExist:
        messages.error(request, "Voter not found or no deletion request pending.")
        return redirect('admin_panel:deletion_requests')
    
    if request.method == 'POST':
        with transaction.atomic():
            # Update action request
            action_request = AccountActionRequest.objects.filter(
                user=voter,
                action_type='DELETE',
                status='PENDING'
            ).first()
            
            if action_request:
                action_request.status = 'APPROVED'
                action_request.processed_by = request.user
                action_request.processed_at = timezone.now()
                action_request.save()
            
            # Send email
            send_account_deletion_confirmation(voter)
            
            # Log
            log_audit_action(
                request.user, 
                f'Approved deletion for: {voter.full_name}', 
                'USER', 
                request
            )
            
            # Delete the account
            voter.delete()
            
            messages.success(request, f"Voter account has been deleted.")
        
        return redirect('admin_panel:deletion_requests')
    
    return redirect('admin_panel:deletion_requests')

@login_required
def reject_deletion(request, voter_id):
    """Reject a voter's account deletion request"""
    if not request.user.can_delete_accounts():
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        voter = User.objects.get(id=voter_id, user_type='VOTER', deletion_requested=True)
    except User.DoesNotExist:
        messages.error(request, "Voter not found or no deletion request pending.")
        return redirect('admin_panel:deletion_requests')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'No reason provided')
        
        with transaction.atomic():
            # Update action request
            action_request = AccountActionRequest.objects.filter(
                user=voter,
                action_type='DELETE',
                status='PENDING'
            ).first()
            
            if action_request:
                action_request.status = 'REJECTED'
                action_request.processed_by = request.user
                action_request.processed_at = timezone.now()
                action_request.reason = reason
                action_request.save()
            
            # Update user
            voter.deletion_requested = False
            voter.deletion_requested_at = None
            voter.deletion_reason = ''
            voter.save()
            
            # Create notification
            create_notification(
                user=voter,
                title='Deletion Request Rejected',
                message=f'Your account deletion request has been rejected. Reason: {reason}',
                notification_type='INFO'
            )
            
            # Send email
            send_account_request_rejected(voter, 'Account Deletion', reason)
            
            # Log
            log_audit_action(
                request.user, 
                f'Rejected deletion for: {voter.full_name}', 
                'USER', 
                request,
                {'reason': reason}
            )
            
            messages.warning(request, f"Deletion request for {voter.full_name} has been rejected.")
        
        return redirect('admin_panel:deletion_requests')
    
    return redirect('admin_panel:deletion_requests')

# ==================== KYC VERIFICATION VIEWS ====================

@method_decorator([login_required], name='dispatch')
class PendingKYCView(ListView):
    """List pending KYC verifications"""
    template_name = 'admin_panel/pending_kyc.html'
    context_object_name = 'pending_kyc'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.can_verify_kyc():
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.filter(
            user_type='VOTER',
            kyc_status='PENDING'
        ).order_by('kyc_submitted_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_pending'] = self.get_queryset().count()
        return context

@method_decorator([login_required], name='dispatch')
class KYCDetailView(DetailView):
    """View KYC details for a voter"""
    model = User
    template_name = 'admin_panel/kyc_detail.html'
    context_object_name = 'voter'
    pk_url_kwarg = 'voter_id'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.can_verify_kyc():
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.filter(user_type='VOTER')

@login_required
def verify_kyc(request, voter_id):
    """Verify a voter's KYC documents"""
    if not request.user.can_verify_kyc():
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        voter = User.objects.get(id=voter_id, user_type='VOTER')
    except User.DoesNotExist:
        messages.error(request, "Voter not found.")
        return redirect('admin_panel:pending_kyc')
    
    if request.method == 'POST':
        voter.kyc_status = 'VERIFIED'
        voter.kyc_verified_at = timezone.now()
        voter.kyc_verified_by = request.user
        voter.id_front_status = 'VERIFIED'
        voter.id_back_status = 'VERIFIED'
        voter.face_photo_status = 'VERIFIED'
        voter.save()
        
        # Create action request
        AccountActionRequest.objects.create(
            user=voter,
            action_type='KYC_VERIFY',
            status='COMPLETED',
            processed_by=request.user,
            processed_at=timezone.now()
        )
        
        # Create notification
        create_notification(
            user=voter,
            title='KYC Verified',
            message='Your KYC documents have been verified successfully.',
            notification_type='SUCCESS'
        )
        
        # Send email
        send_kyc_verification_notice(voter, 'Verified')
        
        log_audit_action(
            request.user, 
            f'Verified KYC for: {voter.full_name}', 
            'KYC', 
            request
        )
        
        messages.success(request, f"KYC for {voter.full_name} has been verified.")
        
        return redirect('admin_panel:pending_kyc')
    
    return redirect('admin_panel:kyc_detail', voter_id=voter_id)

@login_required
def reject_kyc(request, voter_id):
    """Reject a voter's KYC documents"""
    if not request.user.can_verify_kyc():
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        voter = User.objects.get(id=voter_id, user_type='VOTER')
    except User.DoesNotExist:
        messages.error(request, "Voter not found.")
        return redirect('admin_panel:pending_kyc')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'Documents did not meet requirements')
        
        voter.kyc_status = 'REJECTED'
        voter.id_front_status = 'REJECTED'
        voter.id_back_status = 'REJECTED'
        voter.face_photo_status = 'REJECTED'
        voter.save()
        
        # Create action request
        AccountActionRequest.objects.create(
            user=voter,
            action_type='KYC_VERIFY',
            status='REJECTED',
            processed_by=request.user,
            processed_at=timezone.now(),
            reason=reason
        )
        
        # Create notification
        create_notification(
            user=voter,
            title='KYC Rejected',
            message=f'Your KYC documents could not be verified. Reason: {reason}',
            notification_type='WARNING'
        )
        
        # Send email
        send_kyc_verification_notice(voter, 'Rejected')
        
        log_audit_action(
            request.user, 
            f'Rejected KYC for: {voter.full_name}', 
            'KYC', 
            request,
            {'reason': reason}
        )
        
        messages.warning(request, f"KYC for {voter.full_name} has been rejected.")
        
        return redirect('admin_panel:pending_kyc')
    
    return redirect('admin_panel:kyc_detail', voter_id=voter_id)

@login_required
def view_kyc_documents(request, voter_id):
    """View KYC documents for a voter"""
    if not request.user.can_verify_kyc():
        messages.error(request, "You don't have permission to access this page.")
        return redirect('admin_panel:dashboard')
    
    try:
        voter = User.objects.get(id=voter_id, user_type='VOTER')
    except User.DoesNotExist:
        messages.error(request, "Voter not found.")
        return redirect('admin_panel:pending_kyc')
    
    return render(request, 'admin_panel/kyc_documents.html', {'voter': voter})

# ==================== TSC VERIFICATION VIEWS ====================

@method_decorator([login_required], name='dispatch')
class PendingTSCView(ListView):
    """List pending TSC verifications"""
    template_name = 'admin_panel/pending_tsc.html'
    context_object_name = 'pending_tsc'
    paginate_by = 20
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.can_verify_tsc():
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.filter(
            user_type='VOTER',
            tsc_verified=False
        ).order_by('registered_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_pending'] = self.get_queryset().count()
        return context

@login_required
def verify_tsc(request, voter_id):
    """Verify a voter's TSC number"""
    if not request.user.can_verify_tsc():
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        voter = User.objects.get(id=voter_id, user_type='VOTER')
    except User.DoesNotExist:
        messages.error(request, "Voter not found.")
        return redirect('admin_panel:pending_tsc')
    
    if request.method == 'POST':
        voter.tsc_verified = True
        voter.tsc_verified_at = timezone.now()
        voter.tsc_verified_by = request.user
        voter.save()
        
        # Create action request
        AccountActionRequest.objects.create(
            user=voter,
            action_type='TSC_VERIFY',
            status='COMPLETED',
            processed_by=request.user,
            processed_at=timezone.now()
        )
        
        # Create notification
        create_notification(
            user=voter,
            title='TSC Verified',
            message='Your TSC number has been verified successfully.',
            notification_type='SUCCESS'
        )
        
        # Send email
        send_tsc_verification_notice(voter, 'Verified')
        
        log_audit_action(
            request.user, 
            f'Verified TSC for: {voter.full_name}', 
            'KYC', 
            request
        )
        
        messages.success(request, f"TSC number for {voter.full_name} has been verified.")
        
        return redirect('admin_panel:pending_tsc')
    
    return redirect('admin_panel:pending_tsc')

@login_required
def reject_tsc(request, voter_id):
    """Reject a voter's TSC number verification"""
    if not request.user.can_verify_tsc():
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    try:
        voter = User.objects.get(id=voter_id, user_type='VOTER')
    except User.DoesNotExist:
        messages.error(request, "Voter not found.")
        return redirect('admin_panel:pending_tsc')
    
    if request.method == 'POST':
        reason = request.POST.get('reason', 'TSC number could not be verified')
        
        # Create action request
        AccountActionRequest.objects.create(
            user=voter,
            action_type='TSC_VERIFY',
            status='REJECTED',
            processed_by=request.user,
            processed_at=timezone.now(),
            reason=reason
        )
        
        # Create notification
        create_notification(
            user=voter,
            title='TSC Verification Failed',
            message=f'Your TSC number could not be verified. Reason: {reason}',
            notification_type='WARNING'
        )
        
        # Send email
        send_tsc_verification_notice(voter, 'Rejected')
        
        log_audit_action(
            request.user, 
            f'Rejected TSC for: {voter.full_name}', 
            'KYC', 
            request,
            {'reason': reason}
        )
        
        messages.warning(request, f"TSC number for {voter.full_name} could not be verified.")
        
        return redirect('admin_panel:pending_tsc')
    
    return redirect('admin_panel:pending_tsc')

# ==================== KYC/TSC STATISTICS ====================

@login_required
def kyc_statistics(request):
    """Get KYC verification statistics"""
    if not request.user.can_verify_kyc():
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    stats = {
        'pending': User.objects.filter(user_type='VOTER', kyc_status='PENDING').count(),
        'verified': User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count(),
        'rejected': User.objects.filter(user_type='VOTER', kyc_status='REJECTED').count(),
        'incomplete': User.objects.filter(user_type='VOTER', kyc_status='INCOMPLETE').count(),
    }
    
    return JsonResponse(stats)

@login_required
def tsc_statistics(request):
    """Get TSC verification statistics"""
    if not request.user.can_verify_tsc():
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    stats = {
        'verified': User.objects.filter(user_type='VOTER', tsc_verified=True).count(),
        'pending': User.objects.filter(user_type='VOTER', tsc_verified=False).count(),
    }
    
    return JsonResponse(stats)

# ==================== AUDIT LOG VIEWS ====================

@method_decorator([login_required], name='dispatch')
class AuditLogListView(ListView):
    """List audit logs"""
    template_name = 'admin_panel/audit_logs.html'
    context_object_name = 'logs'
    paginate_by = 50
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        queryset = AuditLog.objects.all().select_related('user')
        
        # Filter by user
        user_id = self.request.GET.get('user_id')
        if user_id:
            queryset = queryset.filter(user_id=user_id)
        
        # Filter by action
        action = self.request.GET.get('action')
        if action:
            queryset = queryset.filter(action__icontains=action)
        
        # Filter by category
        category = self.request.GET.get('category')
        if category:
            queryset = queryset.filter(category=category)
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)
        
        date_to = self.request.GET.get('date_to')
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)
        
        return queryset.order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_logs'] = self.get_queryset().count()
        context['categories'] = AuditLog.ACTION_CATEGORIES
        return context

@method_decorator([login_required], name='dispatch')
class AuditLogDetailView(DetailView):
    """View audit log details"""
    model = AuditLog
    template_name = 'admin_panel/audit_log_detail.html'
    context_object_name = 'log'
    pk_url_kwarg = 'log_id'
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)

@login_required
def export_audit_logs(request):
    """Export audit logs as CSV"""
    if request.user.user_type != 'SUPER_ADMIN':
        messages.error(request, "You don't have permission to perform this action.")
        return redirect('admin_panel:dashboard')
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_logs.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Timestamp', 'User', 'Action', 'Category', 'IP Address', 'Details'])
    
    logs = AuditLog.objects.all().select_related('user').order_by('-timestamp')
    
    for log in logs:
        writer.writerow([
            log.timestamp,
            log.user.full_name if log.user else 'System',
            log.action,
            log.category,
            log.ip_address or 'N/A',
            json.dumps(log.details) if log.details else ''
        ])
    
    return response

@method_decorator([login_required], name='dispatch')
class UserAuditLogsView(ListView):
    """View audit logs for a specific user"""
    template_name = 'admin_panel/user_audit_logs.html'
    context_object_name = 'logs'
    paginate_by = 50
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        user_id = self.kwargs.get('user_id')
        return AuditLog.objects.filter(user_id=user_id).select_related('user').order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user_id = self.kwargs.get('user_id')
        context['target_user'] = User.objects.get(id=user_id)
        return context

@method_decorator([login_required], name='dispatch')
class ActionAuditLogsView(ListView):
    """View audit logs for a specific action"""
    template_name = 'admin_panel/action_audit_logs.html'
    context_object_name = 'logs'
    paginate_by = 50
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "You don't have permission to access this page.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        action = self.kwargs.get('action')
        return AuditLog.objects.filter(action__icontains=action).select_related('user').order_by('-timestamp')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['action_filter'] = self.kwargs.get('action')
        return context
    