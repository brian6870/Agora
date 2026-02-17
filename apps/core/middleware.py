import hashlib
import json
from django.utils import timezone
from django.core.cache import cache
from django.http import HttpResponseForbidden, JsonResponse
from django.contrib.auth import logout
from django.conf import settings
from .models import MaintenanceMode
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.deprecation import MiddlewareMixin
import logging

logger = logging.getLogger(__name__)

class DeviceFingerprintMiddleware:
    """
    Middleware to handle device fingerprinting and binding
    """
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Generate fingerprint for this request
        fingerprint = self.get_device_fingerprint(request)
        request.session['device_fingerprint'] = fingerprint
        
        # Check if user is authenticated and device is bound
        if request.user.is_authenticated:
            if request.user.user_type == 'VOTER' and request.user.device_fingerprint:
                # Verify the device matches the bound fingerprint
                if fingerprint != request.user.device_fingerprint:
                    logger.warning(f"Device mismatch for user {request.user.tsc_number}")
                    
                    # Logout the user
                    logout(request)
                    
                    # Redirect to login with error
                    if not request.path.startswith('/accounts/logout/'):
                        from django.contrib import messages
                        from django.shortcuts import redirect
                        messages.error(request, "You can only access your account from your registered device.")
                        return redirect('accounts:login')
        
        response = self.get_response(request)
        return response
    
    def get_device_fingerprint(self, request):
        """
        Generate a consistent fingerprint from browser/device characteristics
        """
        # Collect fingerprint components
        components = {
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'accept_language': request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            'accept_encoding': request.META.get('HTTP_ACCEPT_ENCODING', ''),
            'ip': self.get_client_ip(request),
        }
        
        # Generate hash
        fingerprint_string = json.dumps(components, sort_keys=True)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()
    
    def get_client_ip(self, request):
        """Get client IP address from request"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR', '')
class MaintenanceModeMiddleware(MiddlewareMixin):
    """Middleware to handle maintenance mode"""
    
    def process_request(self, request):
        # Skip for admin paths and static files
        if request.path.startswith('/django-admin/') or \
           request.path.startswith('/admin-panel/') or \
           request.path.startswith('/static/') or \
           request.path.startswith('/media/'):
            return None
        
        try:
            maintenance = MaintenanceMode.objects.first()
            if maintenance and maintenance.is_active:
                # Allow super admins to bypass maintenance
                if request.user.is_authenticated and request.user.user_type == 'SUPER_ADMIN':
                    return None
                
                # Check if IP is allowed
                client_ip = self.get_client_ip(request)
                allowed_ips = maintenance.allowed_ips.split('\n') if maintenance.allowed_ips else []
                allowed_ips = [ip.strip() for ip in allowed_ips if ip.strip()]
                
                if client_ip in allowed_ips:
                    return None
                
                # Check if request is AJAX
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return HttpResponse(
                        json.dumps({'error': 'System is under maintenance'}),
                        content_type='application/json',
                        status=503
                    )
                
                # Show maintenance page
                return render(request, 'core/maintenance.html', {
                    'message': maintenance.message,
                    'estimated_end': maintenance.estimated_end
                }, status=503)
        except:
            pass
        
        return None
    
    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR', '')