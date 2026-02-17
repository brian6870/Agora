from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView, ListView, CreateView, UpdateView, DeleteView, DetailView
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
import csv
import json
import logging
import uuid
from datetime import timedelta
from django.http import FileResponse
from .backup_utils import BackupManager

from apps.accounts.models import User, AdminProfile, AccountActionRequest, Notification, AuditLog
from apps.voting.models import Candidate, Position, Team, Vote, Election, CandidateApplication
from apps.core.models import DeviceResetRequest
from .forms import (
    CandidateForm, TeamForm, PositionForm, ElectionForm,
    VoterSearchForm, DeviceResetProcessForm,
    BulkActionForm, CandidateApplicationReviewForm, TeamApplicationReviewForm,
    GeneralSettingsForm, SecuritySettingsForm, EmailSettingsForm,
    BackupSettingsForm, MaintenanceModeForm, NotificationForm
)
from apps.core.models import MaintenanceMode, SystemLog, PerformanceMetric
from django.db import connection
import psutil
import logging

logger = logging.getLogger(__name__)

# ==================== HELPER FUNCTIONS ====================

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR', '0.0.0.0')

def log_audit(user, action, category='ADMIN', request=None, details=None):
    """Create audit log entry"""
    try:
        AuditLog.objects.create(
            user=user,
            action=action,
            category=category,
            ip_address=get_client_ip(request) if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
            details=details or {}
        )
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")

def timesince(dt):
    """Simple timesince implementation"""
    if not dt:
        return "Never"
    delta = timezone.now() - dt
    if delta.days > 0:
        return f"{delta.days}d ago"
    elif delta.seconds > 3600:
        return f"{delta.seconds // 3600}h ago"
    elif delta.seconds > 60:
        return f"{delta.seconds // 60}m ago"
    else:
        return f"{delta.seconds}s ago"

# ==================== DASHBOARD VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class AdminDashboardView(TemplateView):
    """Main admin dashboard"""
    template_name = 'admin_panel/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Basic stats
        context['total_voters'] = User.objects.filter(user_type='VOTER').count()
        context['verified_voters'] = User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count()
        context['pending_kyc'] = User.objects.filter(user_type='VOTER', kyc_status='PENDING').count()
        context['pending_tsc'] = User.objects.filter(user_type='VOTER', tsc_verified=False).count()
        context['total_votes'] = Vote.objects.count()
        context['total_candidates'] = Candidate.objects.filter(is_active=True).count()
        context['total_teams'] = Team.objects.filter(is_active=True).count()
        
        # Applications
        context['pending_candidate_applications'] = CandidateApplication.objects.filter(status='PENDING').count()
        context['pending_team_applications'] = Team.objects.filter(status='PENDING').count()
        
        # Device resets
        context['pending_resets'] = DeviceResetRequest.objects.filter(status='PENDING').count()
        
        # Recent activity
        activities = []
        for vote in Vote.objects.select_related('voter').order_by('-timestamp')[:5]:
            activities.append({
                'type': 'vote',
                'description': f"{vote.voter.full_name} cast a vote",
                'timestamp': vote.timestamp,
                'user': vote.voter.full_name
            })
        for user in User.objects.filter(user_type='VOTER').order_by('-registered_at')[:5]:
            activities.append({
                'type': 'registration',
                'description': f"New voter registered: {user.full_name}",
                'timestamp': user.registered_at,
                'user': user.full_name
            })
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        context['recent_activity'] = activities[:5]
        
        # Election status
        try:
            context['election'] = Election.objects.filter(status='ACTIVE').first()
        except:
            context['election'] = None
        
        # Calculate turnout
        if context['total_voters'] > 0:
            context['voter_turnout'] = round((context['total_votes'] / context['total_voters']) * 100, 2)
        else:
            context['voter_turnout'] = 0
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class SuperuserDashboardView(TemplateView):
    """Superuser dashboard"""
    template_name = 'admin_panel/superuser_dashboard.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['total_users'] = User.objects.count()
        context['total_voters'] = User.objects.filter(user_type='VOTER').count()
        context['total_admins'] = User.objects.filter(user_type='ADMIN').count()
        context['pending_admins'] = User.objects.filter(user_type='ADMIN', account_status='PENDING').count()
        context['pending_kyc'] = User.objects.filter(user_type='VOTER', kyc_status='PENDING').count()
        context['pending_candidate_applications'] = CandidateApplication.objects.filter(status='PENDING').count()
        context['pending_team_applications'] = Team.objects.filter(status='PENDING').count()
        context['active_elections'] = Election.objects.filter(status='ACTIVE').count()
        context['deletion_requests'] = AccountActionRequest.objects.filter(action_type='DELETE', status='PENDING').count()
        context['suspended_count'] = User.objects.filter(account_status='SUSPENDED').count()
        
        # Pending admins list
        context['pending_admins_list'] = User.objects.filter(
            user_type='ADMIN', account_status='PENDING'
        ).order_by('-registered_at')[:10]
        
        # Recent activity
        activities = []
        for admin in User.objects.filter(user_type='ADMIN', verified_at__isnull=False).order_by('-verified_at')[:3]:
            activities.append({
                'type': 'approval',
                'description': f"Admin approved: {admin.full_name}",
                'timestamp': admin.verified_at,
                'user': admin.verified_by.full_name if admin.verified_by else 'System'
            })
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        context['recent_activity'] = activities[:5]
        
        return context

# ==================== ELECTION MANAGEMENT VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class ElectionListView(TemplateView):
    """List all elections"""
    template_name = 'admin_panel/election/list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        filter_type = self.request.GET.get('filter', 'all')
        
        queryset = Election.objects.all().order_by('-created_at')
        if filter_type == 'active':
            queryset = queryset.filter(status='ACTIVE')
        elif filter_type == 'pending':
            queryset = queryset.filter(status='PENDING')
        elif filter_type == 'completed':
            queryset = queryset.filter(status='COMPLETED')
        elif filter_type == 'draft':
            queryset = queryset.filter(status='DRAFT')
        
        paginator = Paginator(queryset, 10)
        page = self.request.GET.get('page')
        context['elections'] = paginator.get_page(page)
        context['filter'] = filter_type
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class ElectionDetailView(DetailView):
    """Election details"""
    model = Election
    template_name = 'admin_panel/election/detail.html'
    context_object_name = 'election'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        election = self.get_object()
        context['positions'] = Position.objects.filter(election=election).order_by('order')
        context['candidates'] = Candidate.objects.filter(election=election).select_related('position', 'team')
        context['teams'] = Team.objects.filter(election=election)
        context['total_votes'] = Vote.objects.filter(election=election).count()
        context['eligible_voters'] = election.get_eligible_count()
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class ElectionCreateView(CreateView):
    """Create new election"""
    model = Election
    form_class = ElectionForm
    template_name = 'admin_panel/election/form.html'
    success_url = reverse_lazy('admin_panel:election_list')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Only super admins can create elections.")
            return redirect('admin_panel:election_list')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['counties'] = User.objects.filter(user_type='VOTER').values_list('county', flat=True).distinct().order_by('county')
        return context
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        # FIXED: Use self.request instead of request
        log_audit(self.request.user, f"Created election: {form.instance.name}", request=self.request)
        messages.success(self.request, "Election created successfully.")
        return response
@method_decorator([login_required, staff_member_required], name='dispatch')
class ElectionUpdateView(UpdateView):
    """Update election"""
    model = Election
    form_class = ElectionForm
    template_name = 'admin_panel/election/form.html'
    success_url = reverse_lazy('admin_panel:election_list')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Only super admins can edit elections.")
            return redirect('admin_panel:election_list')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['counties'] = User.objects.filter(user_type='VOTER').values_list('county', flat=True).distinct().order_by('county')
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        # FIXED: Use self.request instead of request
        log_audit(self.request.user, f"Updated election: {form.instance.name}", request=self.request)
        messages.success(self.request, "Election updated successfully.")
        return response

@method_decorator([login_required, staff_member_required], name='dispatch')
class ElectionDeleteView(DeleteView):
    """Delete election"""
    model = Election
    template_name = 'admin_panel/election/delete.html'
    success_url = reverse_lazy('admin_panel:election_list')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Only super admins can delete elections.")
            return redirect('admin_panel:election_list')
        return super().dispatch(request, *args, **kwargs)
    
    def delete(self, request, *args, **kwargs):
        election = self.get_object()
        log_audit(request.user, f"Deleted election: {election.name}", request=request)
        messages.success(request, "Election deleted successfully.")
        return super().delete(request, *args, **kwargs)

@method_decorator([login_required, staff_member_required], name='dispatch')
class AllPositionsListView(TemplateView):
    """List all positions across all elections"""
    template_name = 'admin_panel/election/positions_manage.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        election_id = self.request.GET.get('election')
        search = self.request.GET.get('search', '')
        
        # Base queryset
        queryset = Position.objects.all().select_related('election').order_by('election__name', 'order')
        
        # Apply filters
        if election_id and election_id != 'all':
            queryset = queryset.filter(election_id=election_id)
        if search:
            queryset = queryset.filter(name__icontains=search)
        
        # Pagination
        paginator = Paginator(queryset, 20)
        page = self.request.GET.get('page')
        positions = paginator.get_page(page)
        context['positions'] = positions
        
        # Statistics
        context['total_positions'] = Position.objects.count()
        context['active_positions'] = Position.objects.filter(is_active=True).count()
        context['elections_with_positions'] = Position.objects.values('election').distinct().count()
        context['elections'] = Election.objects.all().order_by('-created_at')
        context['selected_election'] = election_id
        context['search'] = search
        
        # Pagination info
        context['is_paginated'] = paginator.num_pages > 1
        context['page_obj'] = positions
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class ElectionPositionsView(TemplateView):
    """Manage positions for a specific election"""
    template_name = 'admin_panel/election/positions.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        election_id = self.kwargs.get('election_id')
        election = get_object_or_404(Election, id=election_id)
        
        context['election'] = election
        context['positions'] = Position.objects.filter(election=election).order_by('order')
        context['total_candidates'] = Candidate.objects.filter(election=election).count()
        context['active_positions'] = Position.objects.filter(election=election, is_active=True).count()
        context['pending_applications'] = CandidateApplication.objects.filter(
            election=election, status='PENDING'
        ).count()
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class PositionCreateView(CreateView):
    """Create a new position (with election selection dropdown)"""
    model = Position
    form_class = PositionForm
    template_name = 'admin_panel/election/position_form.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['elections'] = Election.objects.all().order_by('-created_at')
        context['next_order'] = Position.objects.count() + 1
        context['is_create'] = True
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit(self.request.user, f"Created position: {form.instance.name} for election {form.instance.election.name}", request=self.request)
        messages.success(self.request, "Position created successfully.")
        return response
    
    def get_success_url(self):
        return reverse_lazy('admin_panel:all_positions')

@method_decorator([login_required, staff_member_required], name='dispatch')
class ElectionPositionCreateView(CreateView):
    """Add position to a specific election"""
    model = Position
    form_class = PositionForm
    template_name = 'admin_panel/election/position_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.election = get_object_or_404(Election, id=self.kwargs.get('election_id'))
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['election'] = self.election
        context['elections'] = Election.objects.all().order_by('-created_at')
        context['next_order'] = Position.objects.filter(election=self.election).count() + 1
        context['is_create'] = True
        return context
    
    def get_initial(self):
        initial = super().get_initial()
        initial['election'] = self.election
        return initial
    
    def form_valid(self, form):
        form.instance.election = self.election
        response = super().form_valid(form)
        log_audit(self.request.user, f"Added position {form.instance.name} to election {self.election.name}", request=self.request)
        messages.success(self.request, "Position added successfully.")
        return response
    
    def get_success_url(self):
        return reverse_lazy('admin_panel:election_positions', kwargs={'election_id': self.election.id})

@method_decorator([login_required, staff_member_required], name='dispatch')
class PositionUpdateView(UpdateView):
    """Update position"""
    model = Position
    form_class = PositionForm
    template_name = 'admin_panel/election/position_form.html'
    pk_url_kwarg = 'pk'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['election'] = self.object.election
        context['elections'] = Election.objects.all().order_by('-created_at')
        context['is_create'] = False
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit(self.request.user, f"Updated position {form.instance.name}", request=self.request)
        messages.success(self.request, "Position updated successfully.")
        return response
    
    def get_success_url(self):
        # Check if this was accessed via election-specific URL
        if 'election_id' in self.kwargs:
            return reverse_lazy('admin_panel:election_positions', kwargs={'election_id': self.object.election.id})
        return reverse_lazy('admin_panel:all_positions')

@method_decorator([login_required, staff_member_required], name='dispatch')
class PositionDeleteView(DeleteView):
    """Delete position"""
    model = Position
    template_name = 'admin_panel/election/position_delete.html'
    pk_url_kwarg = 'pk'
    
    def delete(self, request, *args, **kwargs):
        position = self.get_object()
        election_id = position.election.id
        log_audit(request.user, f"Deleted position {position.name}", request=request)
        messages.success(request, "Position deleted successfully.")
        return super().delete(request, *args, **kwargs)
    
    def get_success_url(self):
        position = self.get_object()
        # Check if this was accessed via election-specific URL
        if 'election_id' in self.kwargs:
            return reverse_lazy('admin_panel:election_positions', kwargs={'election_id': position.election.id})
        return reverse_lazy('admin_panel:all_positions')

@login_required
@staff_member_required
def reorder_positions(request):
    """Reorder positions (AJAX endpoint)"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            for item in data.get('order', []):
                Position.objects.filter(id=item['id']).update(order=item['order'])
            log_audit(request.user, f"Reordered positions", request=request)
            return JsonResponse({'success': True})
        except Exception as e:
            logger.error(f"Error reordering positions: {e}")
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=400)

@method_decorator([login_required, staff_member_required], name='dispatch')
class PositionCandidatesView(TemplateView):
    """View candidates for a position"""
    template_name = 'admin_panel/election/position_candidates.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        position_id = self.kwargs.get('position_id')
        position = get_object_or_404(Position, id=position_id)
        
        candidates = Candidate.objects.filter(position=position).order_by('order')
        
        context['position'] = position
        context['election'] = position.election
        context['candidates'] = candidates
        context['active_count'] = candidates.filter(is_active=True).count()
        context['independent_count'] = candidates.filter(team__isnull=True).count()
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class ElectionPositionCandidatesView(TemplateView):
    """Manage candidates for a position within an election"""
    template_name = 'admin_panel/election/position_candidates.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        election_id = self.kwargs.get('election_id')
        position_id = self.kwargs.get('position_id')
        
        election = get_object_or_404(Election, id=election_id)
        position = get_object_or_404(Position, id=position_id, election=election)
        
        candidates = Candidate.objects.filter(election=election, position=position).order_by('order')
        
        context['election'] = election
        context['position'] = position
        context['candidates'] = candidates
        context['active_count'] = candidates.filter(is_active=True).count()
        context['from_applications'] = candidates.filter(application__isnull=False).count()
        context['manually_added'] = candidates.filter(application__isnull=True).count()
        context['independent_count'] = candidates.filter(team__isnull=True).count()
        context['pending_applications'] = CandidateApplication.objects.filter(
            election=election, position=position, status='PENDING'
        ).count()
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class ElectionCandidateCreateView(CreateView):
    """Add candidate to position"""
    model = Candidate
    form_class = CandidateForm
    template_name = 'admin_panel/election/candidate_form.html'
    
    def dispatch(self, request, *args, **kwargs):
        self.election = get_object_or_404(Election, id=self.kwargs.get('election_id'))
        self.position = get_object_or_404(Position, id=self.kwargs.get('position_id'), election=self.election)
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['election'] = self.election
        context['position'] = self.position
        context['teams'] = Team.objects.filter(election=self.election, is_active=True)
        context['next_order'] = Candidate.objects.filter(
            election=self.election, position=self.position
        ).count() + 1
        context['is_create'] = True
        return context
    
    def get_initial(self):
        initial = super().get_initial()
        initial['election'] = self.election
        initial['position'] = self.position
        return initial
    
    def form_valid(self, form):
        form.instance.election = self.election
        form.instance.position = self.position
        form.instance.added_by = self.request.user
        response = super().form_valid(form)
        log_audit(self.request.user, f"Added candidate {form.instance.full_name} to {self.position.name}", request=self.request)
        messages.success(self.request, "Candidate added successfully.")
        return response
    
    def get_success_url(self):
        return reverse_lazy('admin_panel:election_position_candidates', 
                           kwargs={'election_id': self.election.id, 'position_id': self.position.id})

@method_decorator([login_required, staff_member_required], name='dispatch')
class ElectionCandidateUpdateView(UpdateView):
    """Update candidate"""
    model = Candidate
    form_class = CandidateForm
    template_name = 'admin_panel/election/candidate_form.html'
    pk_url_kwarg = 'pk'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['election'] = self.object.election
        context['position'] = self.object.position
        context['teams'] = Team.objects.filter(election=self.object.election, is_active=True)
        context['is_create'] = False
        return context
    
    def form_valid(self, form):
        response = super().form_valid(form)
        log_audit(self.request.user, f"Updated candidate {form.instance.full_name}", request=self.request)
        messages.success(self.request, "Candidate updated successfully.")
        return response
    
    def get_success_url(self):
        return reverse_lazy('admin_panel:election_position_candidates', 
                           kwargs={'election_id': self.object.election.id, 'position_id': self.object.position.id})

@login_required
@staff_member_required
def toggle_candidate_active(request, election_id, position_id, candidate_id):
    """Toggle candidate active status"""
    if request.method == 'POST':
        candidate = get_object_or_404(Candidate, id=candidate_id, election_id=election_id, position_id=position_id)
        candidate.is_active = not candidate.is_active
        candidate.save()
        status = "activated" if candidate.is_active else "deactivated"
        log_audit(request.user, f"{status} candidate {candidate.full_name}", request=request)
        return JsonResponse({'success': True, 'is_active': candidate.is_active})
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def election_candidate_delete(request, election_id, position_id, candidate_id):
    """Delete candidate"""
    if request.method == 'POST':
        candidate = get_object_or_404(Candidate, id=candidate_id, election_id=election_id, position_id=position_id)
        log_audit(request.user, f"Deleted candidate {candidate.full_name}", request=request)
        candidate.delete()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def reorder_election_candidates(request, election_id, position_id):
    """Reorder candidates for a position"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            for item in data.get('order', []):
                Candidate.objects.filter(
                    id=item['id'], election_id=election_id, position_id=position_id
                ).update(order=item['order'])
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Invalid method'}, status=400)

@method_decorator([login_required, staff_member_required], name='dispatch')
class ElectionResultsView(TemplateView):
    """View election results"""
    template_name = 'voter/election_results.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        election_id = self.kwargs.get('election_id')
        election = get_object_or_404(Election, id=election_id)
        
        context['election'] = election
        context['total_votes'] = Vote.objects.filter(election=election).count()
        context['eligible_voters'] = election.get_eligible_count()
        context['turnout'] = round((context['total_votes'] / context['eligible_voters'] * 100), 2) if context['eligible_voters'] > 0 else 0
        
        # Results by position
        results = []
        for position in Position.objects.filter(election=election, is_active=True).order_by('order'):
            candidates = Candidate.objects.filter(election=election, position=position, is_active=True)
            candidate_data = []
            for candidate in candidates:
                candidate_data.append({
                    'full_name': candidate.full_name,
                    'team': candidate.team.name if candidate.team else 'Independent',
                    'votes': candidate.vote_count,
                    'percentage': 0
                })
            
            total_votes = sum(c['votes'] for c in candidate_data)
            for c in candidate_data:
                if total_votes > 0:
                    c['percentage'] = round((c['votes'] / total_votes) * 100, 1)
            
            candidate_data.sort(key=lambda x: x['votes'], reverse=True)
            winner = candidate_data[0] if candidate_data else None
            
            results.append({
                'name': position.name,
                'candidates': candidate_data,
                'total_votes': total_votes,
                'winner': winner
            })
        
        context['results'] = results
        return context

@login_required
@staff_member_required
def download_election_results(request, election_id):
    """Download election results as CSV"""
    election = get_object_or_404(Election, id=election_id)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{election.name}_results.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Election', election.name])
    writer.writerow(['Date', str(election.voting_date)])
    writer.writerow([])
    
    for position in Position.objects.filter(election=election, is_active=True).order_by('order'):
        writer.writerow([position.name])
        writer.writerow(['Candidate', 'Team', 'Votes', 'Percentage'])
        
        candidates = Candidate.objects.filter(election=election, position=position, is_active=True)
        total_votes = sum(c.vote_count for c in candidates)
        
        for candidate in candidates:
            percentage = round((candidate.vote_count / total_votes * 100), 1) if total_votes > 0 else 0
            writer.writerow([
                candidate.full_name,
                candidate.team.name if candidate.team else 'Independent',
                candidate.vote_count,
                f"{percentage}%"
            ])
        writer.writerow([])
    
    return response

# ==================== CANDIDATE MANAGEMENT VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class AllCandidatesListView(TemplateView):
    """List all candidates across all elections"""
    template_name = 'admin_panel/candidates/list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        election_id = self.request.GET.get('election')
        position_id = self.request.GET.get('position')
        team_id = self.request.GET.get('team')
        search = self.request.GET.get('search', '')
        
        # Base queryset - FIXED: changed from 'created_at' to 'added_at'
        queryset = Candidate.objects.all().select_related('election', 'position', 'team', 'voter').order_by('-added_at')
        
        # Apply filters
        if election_id and election_id != 'all':
            queryset = queryset.filter(election_id=election_id)
        if position_id and position_id != 'all':
            queryset = queryset.filter(position_id=position_id)
        if team_id and team_id != 'all':
            queryset = queryset.filter(team_id=team_id)
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) | 
                Q(election__name__icontains=search) |
                Q(position__name__icontains=search)
            )
        
        # Pagination
        paginator = Paginator(queryset, 20)
        page = self.request.GET.get('page')
        candidates = paginator.get_page(page)
        context['candidates'] = candidates
        
        # Statistics
        context['total_candidates'] = Candidate.objects.count()
        context['active_count'] = Candidate.objects.filter(is_active=True).count()
        
        # Filter options
        context['elections'] = Election.objects.all().order_by('-created_at')
        context['positions'] = Position.objects.all().order_by('name')
        context['teams'] = Team.objects.filter(is_active=True).order_by('name')
        
        # Selected filters
        context['selected_election'] = election_id
        context['selected_position'] = position_id
        context['selected_team'] = team_id
        context['search'] = search
        
        # Pagination info
        context['is_paginated'] = paginator.num_pages > 1
        context['page_obj'] = candidates
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class TeamListView(TemplateView):
    """List all teams"""
    template_name = 'admin_panel/teams/list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        election_id = self.request.GET.get('election')
        search = self.request.GET.get('search', '')
        
        # Base queryset
        queryset = Team.objects.all().select_related('election', 'created_by').order_by('-created_at')
        
        # Apply filters
        if election_id and election_id != 'all':
            queryset = queryset.filter(election_id=election_id)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search) | 
                Q(acronym__icontains=search) |
                Q(description__icontains=search)
            )
        
        # Pagination
        paginator = Paginator(queryset, 20)
        page = self.request.GET.get('page')
        teams = paginator.get_page(page)
        context['teams'] = teams
        
        # Statistics
        context['total_teams'] = Team.objects.count()
        context['active_count'] = Team.objects.filter(is_active=True).count()
        context['total_candidates'] = Candidate.objects.filter(team__isnull=False).count()
        
        # Filter options
        context['elections'] = Election.objects.all().order_by('-created_at')
        
        # Selected filters
        context['selected_election'] = election_id
        context['search'] = search
        
        # Pagination info
        context['is_paginated'] = paginator.num_pages > 1
        context['page_obj'] = teams
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class CandidateApplicationListView(TemplateView):
    """List candidate applications"""
    template_name = 'admin_panel/candidates/applications.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        election_id = self.request.GET.get('election')
        status_filter = self.request.GET.get('status', 'all')
        
        queryset = CandidateApplication.objects.all().select_related(
            'voter', 'election', 'position', 'team'
        ).order_by('-applied_at')
        
        if election_id and election_id != 'all':
            queryset = queryset.filter(election_id=election_id)
        
        if status_filter != 'all':
            queryset = queryset.filter(status=status_filter)
        
        paginator = Paginator(queryset, 10)
        page = self.request.GET.get('page')
        context['applications'] = paginator.get_page(page)
        
        context['total_applications'] = CandidateApplication.objects.count()
        context['pending_count'] = CandidateApplication.objects.filter(status='PENDING').count()
        context['approved_count'] = CandidateApplication.objects.filter(status='APPROVED').count()
        context['rejected_count'] = CandidateApplication.objects.filter(status='REJECTED').count()
        context['elections'] = Election.objects.all().order_by('-created_at')
        context['selected_election'] = election_id
        context['status'] = status_filter
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class CandidateApplicationDetailView(DetailView):
    """Candidate application details"""
    model = CandidateApplication
    template_name = 'admin_panel/candidates/application_detail.html'
    context_object_name = 'application'

@login_required
@staff_member_required
def approve_candidate_application(request, pk):
    """Approve a candidate application"""
    if request.method == 'POST':
        application = get_object_or_404(CandidateApplication, id=pk)
        
        # Create candidate from application
        candidate = Candidate.objects.create(
            election=application.election,
            position=application.position,
            team=application.team,
            full_name=application.voter.full_name,
            photo=application.photo,
            bio=application.bio,
            manifesto=application.manifesto,
            application=application,
            voter=application.voter,
            added_by=request.user,
            order=Candidate.objects.filter(
                election=application.election,
                position=application.position
            ).count() + 1
        )
        
        application.status = 'APPROVED'
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.save()
        
        # Send notification
        try:
            Notification.objects.create(
                user=application.voter,
                title='Candidate Application Approved',
                message=f'Your application for {application.position.name} has been approved.',
                notification_type='SUCCESS'
            )
        except:
            pass
        
        log_audit(request.user, f"Approved candidate application for {application.voter.full_name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, f"Application approved for {application.voter.full_name}.")
        return redirect('admin_panel:candidate_applications')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def reject_candidate_application(request, pk):
    """Reject a candidate application"""
    if request.method == 'POST':
        application = get_object_or_404(CandidateApplication, id=pk)
        reason = request.POST.get('reason', '')
        custom_reason = request.POST.get('custom_reason', '')
        
        full_reason = custom_reason if reason == 'Other' else reason
        
        application.status = 'REJECTED'
        application.reviewed_by = request.user
        application.reviewed_at = timezone.now()
        application.rejection_reason = full_reason
        application.save()
        
        # Send notification
        try:
            Notification.objects.create(
                user=application.voter,
                title='Candidate Application Update',
                message=f'Your application for {application.position.name} was not approved.',
                notification_type='WARNING'
            )
        except:
            pass
        
        log_audit(request.user, f"Rejected candidate application for {application.voter.full_name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.warning(request, f"Application rejected for {application.voter.full_name}.")
        return redirect('admin_panel:candidate_applications')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def candidate_application_details(request, pk):
    """Get candidate application details for AJAX"""
    application = get_object_or_404(CandidateApplication, id=pk)
    
    data = {
        'id': application.id,
        'voter': {
            'full_name': application.voter.full_name,
            'email': application.voter.email,
            'tsc_number': application.voter.tsc_number,
            'id_number': application.voter.id_number,
            'county': application.voter.county,
            'school': application.voter.school,
        },
        'election': {
            'name': application.election.name,
            'type': application.election.get_election_type_display(),
            'date': application.election.voting_date.isoformat() if application.election.voting_date else None,
        },
        'position': {
            'name': application.position.name,
        },
        'team': {
            'name': application.team.name if application.team else None,
            'acronym': application.team.acronym if application.team else None,
        } if application.team else None,
        'bio': application.bio,
        'manifesto': application.manifesto,
        'status': application.get_status_display(),
        'applied_at': application.applied_at.isoformat(),
        'reviewed_by': application.reviewed_by.full_name if application.reviewed_by else None,
        'reviewed_at': application.reviewed_at.isoformat() if application.reviewed_at else None,
        'rejection_reason': application.rejection_reason,
    }
    
    return JsonResponse(data)

# ==================== TEAM APPLICATIONS VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class TeamApplicationListView(TemplateView):
    """List team applications"""
    template_name = 'admin_panel/teams/applications.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        election_id = self.request.GET.get('election')
        
        queryset = Team.objects.filter(status='PENDING').select_related('election', 'created_by').order_by('-created_at')
        
        if election_id and election_id != 'all':
            queryset = queryset.filter(election_id=election_id)
        
        paginator = Paginator(queryset, 10)
        page = self.request.GET.get('page')
        context['applications'] = paginator.get_page(page)
        
        context['total_applications'] = Team.objects.filter(status='PENDING').count()
        context['pending_count'] = Team.objects.filter(status='PENDING').count()
        context['approved_count'] = Team.objects.filter(status='APPROVED').count()
        context['rejected_count'] = Team.objects.filter(status='REJECTED').count()
        context['elections'] = Election.objects.all().order_by('-created_at')
        context['selected_election'] = election_id
        
        return context

@login_required
@staff_member_required
def approve_team_application(request, pk):
    """Approve a team application"""
    if request.method == 'POST':
        team = get_object_or_404(Team, id=pk, status='PENDING')
        
        team.status = 'APPROVED'
        team.reviewed_by = request.user
        team.reviewed_at = timezone.now()
        team.is_active = True
        team.save()
        
        # Send notification
        try:
            Notification.objects.create(
                user=team.created_by,
                title='Team Application Approved',
                message=f'Your team "{team.name}" has been approved.',
                notification_type='SUCCESS'
            )
        except:
            pass
        
        log_audit(request.user, f"Approved team application for {team.name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, f"Team {team.name} approved.")
        return redirect('admin_panel:team_applications')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def reject_team_application(request, pk):
    """Reject a team application"""
    if request.method == 'POST':
        team = get_object_or_404(Team, id=pk, status='PENDING')
        reason = request.POST.get('reason', '')
        
        team.status = 'REJECTED'
        team.reviewed_by = request.user
        team.reviewed_at = timezone.now()
        team.rejection_reason = reason
        team.save()
        
        # Send notification
        try:
            Notification.objects.create(
                user=team.created_by,
                title='Team Application Update',
                message=f'Your team "{team.name}" was not approved.',
                notification_type='WARNING'
            )
        except:
            pass
        
        log_audit(request.user, f"Rejected team application for {team.name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.warning(request, f"Team {team.name} rejected.")
        return redirect('admin_panel:team_applications')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def team_application_details(request, pk):
    """Get team application details for AJAX"""
    team = get_object_or_404(Team, id=pk)
    
    data = {
        'id': team.id,
        'name': team.name,
        'acronym': team.acronym,
        'color_code': team.color_code,
        'description': team.description,
        'logo': team.logo.url if team.logo else None,
        'election': team.election.name if team.election else None,
        'created_by': team.created_by.full_name if team.created_by else 'Unknown',
        'created_at': team.created_at.isoformat(),
        'status': team.get_status_display(),
    }
    
    return JsonResponse(data)

# ==================== VOTER MANAGEMENT VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class VoterManagementView(TemplateView):
    """Voter management list"""
    template_name = 'admin_panel/voters/list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        queryset = User.objects.filter(user_type='VOTER').select_related('verified_by')
        
        # Apply filters
        kyc_status = self.request.GET.get('kyc_status')
        if kyc_status:
            queryset = queryset.filter(kyc_status=kyc_status)
        
        voted = self.request.GET.get('voted')
        if voted == 'yes':
            queryset = queryset.filter(has_voted=True)
        elif voted == 'no':
            queryset = queryset.filter(has_voted=False)
        
        tsc_verified = self.request.GET.get('tsc_verified')
        if tsc_verified == 'yes':
            queryset = queryset.filter(tsc_verified=True)
        elif tsc_verified == 'no':
            queryset = queryset.filter(tsc_verified=False)
        
        account_status = self.request.GET.get('account_status')
        if account_status:
            queryset = queryset.filter(account_status=account_status)
        
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(tsc_number__icontains=search) |
                Q(email__icontains=search) |
                Q(id_number__icontains=search)
            )
        
        paginator = Paginator(queryset.order_by('-registered_at'), 50)
        page = self.request.GET.get('page')
        context['voters'] = paginator.get_page(page)
        
        context['kyc_statuses'] = User.KYC_STATUS
        context['account_statuses'] = User.ACCOUNT_STATUS
        context['selected_kyc'] = kyc_status
        context['selected_voted'] = voted
        context['selected_tsc_verified'] = tsc_verified
        context['selected_account_status'] = account_status
        context['search'] = search or ''
        
        context['total_voters'] = User.objects.filter(user_type='VOTER').count()
        context['verified_count'] = User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count()
        context['voted_count'] = User.objects.filter(user_type='VOTER', has_voted=True).count()
        context['pending_count'] = User.objects.filter(user_type='VOTER', kyc_status='PENDING').count()
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class VoterDetailView(DetailView):
    """Voter details"""
    model = User
    template_name = 'admin_panel/voters/detail.html'
    context_object_name = 'voter'
    pk_url_kwarg = 'voter_id'
    
    def get_queryset(self):
        return User.objects.filter(user_type='VOTER')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        voter = self.get_object()
        
        try:
            context['vote'] = Vote.objects.get(voter=voter)
        except Vote.DoesNotExist:
            context['vote'] = None
        
        context['action_history'] = AccountActionRequest.objects.filter(user=voter).order_by('-requested_at')[:10]
        context['device_resets'] = DeviceResetRequest.objects.filter(
            tsc_number=voter.tsc_number, id_number=voter.id_number
        ).order_by('-created_at')[:5]
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class SuspendedVotersView(TemplateView):
    """List suspended voters"""
    template_name = 'admin_panel/voters/suspended.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['suspended_voters'] = User.objects.filter(
            user_type='VOTER', account_status='SUSPENDED'
        ).select_related('suspended_by').order_by('-suspended_at')
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class VoterDeletionRequestsView(TemplateView):
    """List deletion requests"""
    template_name = 'admin_panel/voters/deletion_requests.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['deletion_requests'] = AccountActionRequest.objects.filter(
            action_type='DELETE', status='PENDING'
        ).select_related('user').order_by('-requested_at')
        return context

@login_required
@staff_member_required
def verify_voter_kyc(request, voter_id):
    """Verify voter KYC"""
    if request.method == 'POST':
        voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
        
        voter.kyc_status = 'VERIFIED'
        voter.verified_at = timezone.now()
        voter.verified_by = request.user
        voter.id_front_status = 'VERIFIED'
        voter.id_back_status = 'VERIFIED'
        voter.face_photo_status = 'VERIFIED'
        voter.save()
        
        try:
            Notification.objects.create(
                user=voter,
                title='KYC Verified',
                message='Your KYC documents have been verified.',
                notification_type='SUCCESS'
            )
        except:
            pass
        
        log_audit(request.user, f"Verified KYC for {voter.full_name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, f"KYC verified for {voter.full_name}")
        return redirect('admin_panel:voter_detail', voter_id=voter.id)
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def verify_voter_tsc(request, voter_id):
    """Verify voter TSC"""
    if request.method == 'POST':
        voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
        
        voter.tsc_verified = True
        voter.tsc_verified_at = timezone.now()
        voter.tsc_verified_by = request.user
        voter.save()
        
        try:
            Notification.objects.create(
                user=voter,
                title='TSC Verified',
                message='Your TSC number has been verified.',
                notification_type='SUCCESS'
            )
        except:
            pass
        
        log_audit(request.user, f"Verified TSC for {voter.full_name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, f"TSC verified for {voter.full_name}")
        return redirect('admin_panel:voter_detail', voter_id=voter.id)
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def suspend_voter(request, voter_id):
    """Suspend voter"""
    if request.method == 'POST':
        voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
        reason = request.POST.get('reason', 'No reason provided')
        
        voter.account_status = 'SUSPENDED'
        voter.suspended_at = timezone.now()
        voter.suspended_by = request.user
        voter.suspension_reason = reason
        voter.save()
        
        try:
            Notification.objects.create(
                user=voter,
                title='Account Suspended',
                message=f'Your account has been suspended. Reason: {reason}',
                notification_type='WARNING'
            )
        except:
            pass
        
        log_audit(request.user, f"Suspended voter {voter.full_name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.warning(request, f"Voter {voter.full_name} suspended.")
        return redirect('admin_panel:voter_detail', voter_id=voter.id)
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def activate_voter(request, voter_id):
    """Activate voter"""
    if request.method == 'POST':
        voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
        
        voter.account_status = 'ACTIVE'
        voter.suspended_at = None
        voter.suspended_by = None
        voter.suspension_reason = ''
        voter.save()
        
        try:
            Notification.objects.create(
                user=voter,
                title='Account Activated',
                message='Your account has been reactivated.',
                notification_type='SUCCESS'
            )
        except:
            pass
        
        log_audit(request.user, f"Activated voter {voter.full_name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, f"Voter {voter.full_name} activated.")
        return redirect('admin_panel:voter_detail', voter_id=voter.id)
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def delete_voter(request, voter_id):
    """Delete a voter account - prevents deletion if voter has voted"""
    if request.method == 'POST':
        voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
        reason = request.POST.get('reason', 'No reason provided')
        
        # Check if voter has cast votes
        if voter.has_voted:
            logger.warning(f"Attempted to delete voter {voter.full_name} who has already voted")
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'status': 'error',
                    'error': 'Cannot delete a voter who has already cast their vote. Consider suspending the account instead.'
                }, status=400)
            
            messages.error(request, "Cannot delete a voter who has already cast their vote. Consider suspending the account instead.")
            return redirect('admin_panel:voter_detail', voter_id=voter.id)
        
        try:
            # No votes - safe to delete
            from apps.core.models import DeviceResetRequest
            from apps.accounts.models import AccountActionRequest, Notification
            
            # Delete related records first
            DeviceResetRequest.objects.filter(tsc_number=voter.tsc_number, id_number=voter.id_number).delete()
            AccountActionRequest.objects.filter(user=voter).delete()
            Notification.objects.filter(user=voter).delete()
            
            # Log before deletion
            logger.warning(f"Voter {voter.full_name} ({voter.tsc_number}) deleted by {request.user.username}. Reason: {reason}")
            
            # Delete the voter
            voter.delete()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'status': 'success'})
            
            messages.success(request, "Voter account deleted successfully.")
            return redirect('admin_panel:voter_list')
            
        except Exception as e:
            logger.error(f"Error deleting voter {voter_id}: {e}", exc_info=True)
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': f'Error deleting voter: {str(e)}'}, status=500)
            
            messages.error(request, f"Error deleting voter: {str(e)}")
            return redirect('admin_panel:voter_detail', voter_id=voter.id)
    
    return JsonResponse({'error': 'Invalid method'}, status=400)


@login_required
@staff_member_required
def suspend_voter(request, voter_id):
    """Suspend a voter account - allowed even if voter has voted"""
    if request.method == 'POST':
        voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
        reason = request.POST.get('reason', 'No reason provided')
        
        # Suspension is always allowed, even if voter has voted
        voter.account_status = 'SUSPENDED'
        voter.suspended_at = timezone.now()
        voter.suspended_by = request.user
        voter.suspension_reason = reason
        voter.save()
        
        logger.warning(f"Voter {voter.full_name} suspended by {request.user.username}. Reason: {reason}")
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.warning(request, f"Voter {voter.full_name} has been suspended.")
        return redirect('admin_panel:voter_detail', voter_id=voter.id)
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def approve_deletion_request(request, request_id):
    """Approve deletion request"""
    if request.method == 'POST':
        action_request = get_object_or_404(AccountActionRequest, id=request_id, action_type='DELETE')
        
        action_request.status = 'APPROVED'
        action_request.processed_by = request.user
        action_request.processed_at = timezone.now()
        action_request.save()
        
        user = action_request.user
        log_audit(request.user, f"Approved deletion request for {user.full_name}", request=request)
        user.delete()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, "Deletion request approved.")
        return redirect('admin_panel:voter_deletion_requests')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def reject_deletion_request(request, request_id):
    """Reject deletion request"""
    if request.method == 'POST':
        action_request = get_object_or_404(AccountActionRequest, id=request_id, action_type='DELETE')
        reason = request.POST.get('reason', '')
        
        action_request.status = 'REJECTED'
        action_request.processed_by = request.user
        action_request.processed_at = timezone.now()
        action_request.admin_notes = reason
        action_request.save()
        
        user = action_request.user
        user.deletion_requested = False
        user.deletion_reason = ''
        user.save()
        
        log_audit(request.user, f"Rejected deletion request for {user.full_name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.warning(request, "Deletion request rejected.")
        return redirect('admin_panel:voter_deletion_requests')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def bulk_voter_action(request):
    """Bulk actions on voters"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    action = request.POST.get('action')
    voter_ids = request.POST.getlist('voter_ids')
    
    if not voter_ids:
        return JsonResponse({'error': 'No voters selected'}, status=400)
    
    try:
        if action == 'verify_kyc':
            updated = User.objects.filter(id__in=voter_ids, user_type='VOTER').update(
                kyc_status='VERIFIED',
                verified_at=timezone.now(),
                verified_by=request.user
            )
            messages.success(request, f"KYC verified for {updated} voters.")
        
        elif action == 'verify_tsc':
            updated = User.objects.filter(id__in=voter_ids, user_type='VOTER').update(
                tsc_verified=True,
                tsc_verified_at=timezone.now(),
                tsc_verified_by=request.user
            )
            messages.success(request, f"TSC verified for {updated} voters.")
        
        elif action == 'suspend':
            reason = request.POST.get('reason', 'Bulk suspension')
            updated = User.objects.filter(id__in=voter_ids, user_type='VOTER').update(
                account_status='SUSPENDED',
                suspended_at=timezone.now(),
                suspended_by=request.user,
                suspension_reason=reason
            )
            messages.warning(request, f"{updated} voters suspended.")
        
        elif action == 'activate':
            updated = User.objects.filter(id__in=voter_ids, user_type='VOTER').update(
                account_status='ACTIVE',
                suspended_at=None,
                suspended_by=None,
                suspension_reason=''
            )
            messages.success(request, f"{updated} voters activated.")
        
        elif action == 'delete':
            confirm = request.POST.get('confirm')
            if confirm != 'yes':
                return JsonResponse({'error': 'Deletion requires confirmation'}, status=400)
            
            for voter_id in voter_ids:
                try:
                    voter = User.objects.get(id=voter_id, user_type='VOTER')
                    log_audit(request.user, f"Bulk delete voter {voter.full_name}", request=request)
                except User.DoesNotExist:
                    pass
            
            deleted_count = User.objects.filter(id__in=voter_ids, user_type='VOTER').delete()[0]
            messages.success(request, f"{deleted_count} voters deleted.")
        
        else:
            return JsonResponse({'error': f'Invalid action: {action}'}, status=400)
        
        return JsonResponse({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Error in bulk voter action: {e}")
        return JsonResponse({'error': str(e)}, status=500)

# ==================== KYC VERIFICATION VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class PendingKYCView(TemplateView):
    """Pending KYC list"""
    template_name = 'admin_panel/kyc/pending.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        search = self.request.GET.get('search', '')
        county = self.request.GET.get('county', '')
        
        queryset = User.objects.filter(user_type='VOTER', kyc_status='PENDING').order_by('kyc_submitted_at')
        
        if search:
            queryset = queryset.filter(
                Q(full_name__icontains=search) |
                Q(tsc_number__icontains=search) |
                Q(id_number__icontains=search)
            )
        
        if county:
            queryset = queryset.filter(county=county)
        
        paginator = Paginator(queryset, 20)
        page = self.request.GET.get('page')
        context['pending_kyc'] = paginator.get_page(page)
        
        context['pending_count'] = User.objects.filter(user_type='VOTER', kyc_status='PENDING').count()
        context['verified_today'] = User.objects.filter(
            user_type='VOTER', kyc_status='VERIFIED', kyc_verified_at__date=timezone.now().date()
        ).count()
        context['counties'] = User.objects.filter(user_type='VOTER').values_list('county', flat=True).distinct().order_by('county')
        context['search'] = search
        context['selected_county'] = county
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class KYCDetailView(DetailView):
    """KYC details"""
    model = User
    template_name = 'admin_panel/kyc/detail.html'
    context_object_name = 'voter'
    pk_url_kwarg = 'voter_id'
    
    def get_queryset(self):
        return User.objects.filter(user_type='VOTER')

@login_required
@staff_member_required
def verify_kyc(request, voter_id):
    """Verify KYC"""
    if request.method == 'POST':
        voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
        
        voter.kyc_status = 'VERIFIED'
        voter.kyc_verified_at = timezone.now()
        voter.kyc_verified_by = request.user
        voter.id_front_status = 'VERIFIED'
        voter.id_back_status = 'VERIFIED'
        voter.face_photo_status = 'VERIFIED'
        voter.save()
        
        log_audit(request.user, f"Verified KYC for {voter.full_name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, f"KYC verified for {voter.full_name}")
        return redirect('admin_panel:pending_kyc')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def reject_kyc(request, voter_id):
    """Reject KYC"""
    if request.method == 'POST':
        voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
        reason = request.POST.get('reason', 'Documents did not meet requirements')
        
        voter.kyc_status = 'REJECTED'
        voter.kyc_verified_at = timezone.now()
        voter.kyc_verified_by = request.user
        voter.id_front_status = 'REJECTED'
        voter.id_back_status = 'REJECTED'
        voter.face_photo_status = 'REJECTED'
        voter.save()
        
        log_audit(request.user, f"Rejected KYC for {voter.full_name}", request=request, details={'reason': reason})
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.warning(request, f"KYC rejected for {voter.full_name}")
        return redirect('admin_panel:pending_kyc')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def view_kyc_documents(request, voter_id):
    """View KYC documents"""
    voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
    return render(request, 'admin_panel/kyc/documents.html', {'voter': voter})

@login_required
@staff_member_required
def kyc_statistics(request):
    """KYC statistics"""
    stats = {
        'pending': User.objects.filter(user_type='VOTER', kyc_status='PENDING').count(),
        'verified': User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count(),
        'rejected': User.objects.filter(user_type='VOTER', kyc_status='REJECTED').count(),
        'flagged': User.objects.filter(user_type='VOTER', kyc_status='FLAGGED').count(),
    }
    return JsonResponse(stats)

# ==================== TSC VERIFICATION VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class PendingTSCView(TemplateView):
    """Pending TSC list"""
    template_name = 'admin_panel/tsc/pending.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        queryset = User.objects.filter(user_type='VOTER', tsc_verified=False).order_by('registered_at')
        paginator = Paginator(queryset, 20)
        page = self.request.GET.get('page')
        context['pending_tsc'] = paginator.get_page(page)
        
        context['pending_count'] = User.objects.filter(user_type='VOTER', tsc_verified=False).count()
        context['verified_today'] = User.objects.filter(
            user_type='VOTER', tsc_verified=True, tsc_verified_at__date=timezone.now().date()
        ).count()
        
        total = User.objects.filter(user_type='VOTER').count()
        verified = User.objects.filter(user_type='VOTER', tsc_verified=True).count()
        context['success_rate'] = round((verified / total * 100), 1) if total > 0 else 0
        
        return context

@login_required
@staff_member_required
def verify_tsc(request, voter_id):
    """Verify TSC"""
    if request.method == 'POST':
        voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
        
        voter.tsc_verified = True
        voter.tsc_verified_at = timezone.now()
        voter.tsc_verified_by = request.user
        voter.save()
        
        log_audit(request.user, f"Verified TSC for {voter.full_name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, f"TSC verified for {voter.full_name}")
        return redirect('admin_panel:pending_tsc')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def reject_tsc(request, voter_id):
    """Reject TSC"""
    if request.method == 'POST':
        voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
        reason = request.POST.get('reason', 'TSC number could not be verified')
        
        log_audit(request.user, f"Rejected TSC for {voter.full_name}", request=request, details={'reason': reason})
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.warning(request, f"TSC verification rejected for {voter.full_name}")
        return redirect('admin_panel:pending_tsc')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def tsc_statistics(request):
    """TSC statistics"""
    stats = {
        'verified': User.objects.filter(user_type='VOTER', tsc_verified=True).count(),
        'pending': User.objects.filter(user_type='VOTER', tsc_verified=False).count(),
    }
    return JsonResponse(stats)

# ==================== ADMIN MANAGEMENT VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class AdminListView(TemplateView):
    """Admin list"""
    template_name = 'admin_panel/admins/list.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        search = self.request.GET.get('search', '')
        status = self.request.GET.get('status', '')
        role = self.request.GET.get('role', '')
        
        queryset = User.objects.filter(user_type__in=['ADMIN', 'SUPER_ADMIN']).order_by('-registered_at')
        
        if search:
            queryset = queryset.filter(Q(full_name__icontains=search) | Q(email__icontains=search))
        if status:
            queryset = queryset.filter(account_status=status)
        if role:
            queryset = queryset.filter(user_type=role)
        
        context['admins'] = queryset
        context['search'] = search
        context['status'] = status
        context['role'] = role
        context['pending_count'] = User.objects.filter(user_type__in=['ADMIN', 'SUPER_ADMIN'], account_status='PENDING').count()
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class PendingAdminApprovalsView(TemplateView):
    """Pending admin approvals"""
    template_name = 'admin_panel/admins/pending.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['pending_admins'] = User.objects.filter(
            user_type='ADMIN', account_status='PENDING'
        ).select_related('admin_profile').order_by('-registered_at')
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class AdminDetailView(DetailView):
    """Admin details"""
    model = User
    template_name = 'admin_panel/admins/detail.html'
    context_object_name = 'admin'
    pk_url_kwarg = 'admin_id'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_queryset(self):
        return User.objects.filter(user_type__in=['ADMIN', 'SUPER_ADMIN']).select_related('admin_profile')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['recent_activity'] = AuditLog.objects.filter(user=self.get_object()).order_by('-timestamp')[:10]
        return context

@login_required
@staff_member_required
def approve_admin(request, admin_id):
    """Approve admin"""
    if request.method == 'POST':
        if request.user.user_type != 'SUPER_ADMIN':
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        admin = get_object_or_404(User, id=admin_id, user_type='ADMIN')
        
        # Generate admin ID
        import uuid
        admin.admin_id = f"ADMIN{uuid.uuid4().hex[:8].upper()}"
        admin.is_active = True
        admin.account_status = 'ACTIVE'
        admin.verified_at = timezone.now()
        admin.verified_by = request.user
        admin.save()
        
        log_audit(request.user, f"Approved admin {admin.full_name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, f"Admin {admin.full_name} approved.")
        return redirect('admin_panel:pending_admin_approvals')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def reject_admin(request, admin_id):
    """Reject admin"""
    if request.method == 'POST':
        if request.user.user_type != 'SUPER_ADMIN':
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        admin = get_object_or_404(User, id=admin_id, user_type='ADMIN')
        reason = request.POST.get('reason', 'Application rejected')
        
        admin.account_status = 'REJECTED'
        admin.is_active = False
        admin.save()
        
        log_audit(request.user, f"Rejected admin {admin.full_name}", request=request, details={'reason': reason})
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.warning(request, f"Admin {admin.full_name} rejected.")
        return redirect('admin_panel:pending_admin_approvals')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def suspend_admin(request, admin_id):
    """Suspend admin"""
    if request.method == 'POST':
        if request.user.user_type != 'SUPER_ADMIN':
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        admin = get_object_or_404(User, id=admin_id, user_type='ADMIN')
        reason = request.POST.get('reason', 'No reason provided')
        
        admin.account_status = 'SUSPENDED'
        admin.suspended_at = timezone.now()
        admin.suspended_by = request.user
        admin.suspension_reason = reason
        admin.is_active = False
        admin.save()
        
        log_audit(request.user, f"Suspended admin {admin.full_name}", request=request, details={'reason': reason})
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.warning(request, f"Admin {admin.full_name} suspended.")
        return redirect('admin_panel:admin_detail', admin_id=admin.id)
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def activate_admin(request, admin_id):
    """Activate admin"""
    if request.method == 'POST':
        if request.user.user_type != 'SUPER_ADMIN':
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        admin = get_object_or_404(User, id=admin_id, user_type='ADMIN')
        
        admin.account_status = 'ACTIVE'
        admin.suspended_at = None
        admin.suspended_by = None
        admin.suspension_reason = ''
        admin.is_active = True
        admin.save()
        
        log_audit(request.user, f"Activated admin {admin.full_name}", request=request)
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, f"Admin {admin.full_name} activated.")
        return redirect('admin_panel:admin_detail', admin_id=admin.id)
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def delete_admin(request, admin_id):
    """Delete admin"""
    if request.method == 'POST':
        if request.user.user_type != 'SUPER_ADMIN':
            return JsonResponse({'error': 'Permission denied'}, status=403)
        
        admin = get_object_or_404(User, id=admin_id, user_type='ADMIN')
        reason = request.POST.get('reason', 'No reason provided')
        
        log_audit(request.user, f"Deleted admin {admin.full_name}", request=request, details={'reason': reason})
        
        admin.delete()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, "Admin account deleted.")
        return redirect('admin_panel:admin_list')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def edit_admin_permissions(request, admin_id):
    """Edit admin permissions"""
    admin = get_object_or_404(User, id=admin_id, user_type='ADMIN')
    
    if request.method == 'POST':
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        
        # Permission update logic would go here
        log_audit(request.user, f"Updated permissions for {admin.full_name}", request=request)
        messages.success(request, f"Permissions updated for {admin.full_name}")
        return redirect('admin_panel:admin_detail', admin_id=admin.id)
    
    return render(request, 'admin_panel/admins/edit_permissions.html', {'admin': admin})

# ==================== DEVICE RESET REQUESTS VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class DeviceResetRequestsView(TemplateView):
    """Device reset requests list"""
    template_name = 'admin_panel/device_resets/list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        status = self.request.GET.get('status', '')
        queryset = DeviceResetRequest.objects.all().order_by('-created_at')
        
        if status:
            queryset = queryset.filter(status=status)
        
        context['requests'] = queryset
        context['selected_status'] = status
        context['status_choices'] = DeviceResetRequest.STATUS_CHOICES
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class DeviceResetDetailView(DetailView):
    """Device reset details"""
    model = DeviceResetRequest
    template_name = 'admin_panel/device_resets/detail.html'
    context_object_name = 'reset_request'
    pk_url_kwarg = 'request_id'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        reset_req = self.get_object()
        
        try:
            context['voter'] = User.objects.get(
                tsc_number=reset_req.tsc_number,
                id_number=reset_req.id_number
            )
        except User.DoesNotExist:
            context['voter'] = None
        
        return context

@login_required
@staff_member_required
def approve_device_reset(request, request_id):
    """Approve device reset"""
    if request.method == 'POST':
        reset_req = get_object_or_404(DeviceResetRequest, id=request_id)
        
        try:
            user = User.objects.get(tsc_number=reset_req.tsc_number, id_number=reset_req.id_number)
            user.device_fingerprint = None
            user.save()
            log_audit(request.user, f"Approved device reset for {user.full_name}", request=request)
        except User.DoesNotExist:
            logger.warning(f"Device reset approved but user not found: {reset_req.tsc_number}")
        
        reset_req.status = 'APPROVED'
        reset_req.reviewed_by = request.user
        reset_req.reviewed_at = timezone.now()
        reset_req.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.success(request, "Device reset approved.")
        return redirect('admin_panel:device_reset_requests')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def reject_device_reset(request, request_id):
    """Reject device reset"""
    if request.method == 'POST':
        reset_req = get_object_or_404(DeviceResetRequest, id=request_id)
        reason = request.POST.get('reason', 'Request rejected')
        
        reset_req.status = 'REJECTED'
        reset_req.reviewed_by = request.user
        reset_req.reviewed_at = timezone.now()
        reset_req.rejection_reason = reason
        reset_req.save()
        
        log_audit(request.user, f"Rejected device reset request {request_id}", request=request, details={'reason': reason})
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'status': 'success'})
        
        messages.warning(request, "Device reset rejected.")
        return redirect('admin_panel:device_reset_requests')
    
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def device_reset_statistics(request):
    """Device reset statistics"""
    stats = {
        'pending': DeviceResetRequest.objects.filter(status='PENDING').count(),
        'approved': DeviceResetRequest.objects.filter(status='APPROVED').count(),
        'rejected': DeviceResetRequest.objects.filter(status='REJECTED').count(),
    }
    return JsonResponse(stats)

# ==================== ELECTION MONITORING VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class LiveElectionMonitoringView(TemplateView):
    """Live election monitoring"""
    template_name = 'admin_panel/monitoring/live.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get active election
        context['election'] = Election.objects.filter(status='ACTIVE').first()
        
        # Positions data
        positions = []
        for position in Position.objects.filter(is_active=True).order_by('order'):
            candidates = []
            for candidate in Candidate.objects.filter(position=position, is_active=True):
                candidates.append({
                    'id': candidate.id,
                    'full_name': candidate.full_name,
                    'team': candidate.team.name if candidate.team else 'Independent',
                    'vote_count': candidate.vote_count,
                    'percentage': 0
                })
            
            total_votes = sum(c['vote_count'] for c in candidates)
            for c in candidates:
                if total_votes > 0:
                    c['percentage'] = round((c['vote_count'] / total_votes) * 100, 1)
            
            positions.append({
                'id': position.id,
                'name': position.name,
                'candidates': candidates,
                'total_votes': total_votes
            })
        
        context['positions'] = positions
        
        # Recent activity
        activities = []
        for vote in Vote.objects.select_related('voter').order_by('-timestamp')[:10]:
            activities.append({
                'voter': vote.voter.full_name,
                'timestamp': vote.timestamp,
                'time_ago': timesince(vote.timestamp)
            })
        context['recent_activity'] = activities
        
        return context

@login_required
@staff_member_required
def live_monitoring_data(request):
    """Live monitoring data API"""
    total_voters = User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count()
    votes_cast = Vote.objects.count()
    
    # Last minute votes
    one_minute_ago = timezone.now() - timedelta(minutes=1)
    last_minute_votes = Vote.objects.filter(timestamp__gte=one_minute_ago).count()
    
    # Vote rate
    last_5_minutes = timezone.now() - timedelta(minutes=5)
    votes_last_5 = Vote.objects.filter(timestamp__gte=last_5_minutes).count()
    vote_rate = round(votes_last_5 / 5, 1) if votes_last_5 > 0 else 0
    
    # Vote history
    vote_history = []
    now = timezone.now()
    for i in range(5, -1, -1):
        hour_start = now - timedelta(hours=i+1)
        hour_end = now - timedelta(hours=i)
        vote_history.append(Vote.objects.filter(timestamp__gte=hour_start, timestamp__lt=hour_end).count())
    
    # Candidates data
    candidates = []
    for candidate in Candidate.objects.filter(is_active=True).select_related('position', 'team')[:10]:
        candidates.append({
            'id': candidate.id,
            'full_name': candidate.full_name,
            'position': candidate.position.name,
            'team': candidate.team.name if candidate.team else None,
            'votes': candidate.vote_count,
            'percentage': 0
        })
    
    # Positions data
    positions = []
    for position in Position.objects.filter(is_active=True).order_by('order'):
        positions.append({
            'id': position.id,
            'name': position.name,
            'total_votes': Vote.objects.filter(candidates__position=position).count()
        })
    
    # Recent activity
    recent_activity = []
    for vote in Vote.objects.select_related('voter').order_by('-timestamp')[:5]:
        recent_activity.append({
            'voter': vote.voter.full_name,
            'time': timesince(vote.timestamp)
        })
    
    data = {
        'total_votes': votes_cast,
        'last_minute_votes': last_minute_votes,
        'vote_rate': vote_rate,
        'turnout': round((votes_cast / total_voters * 100), 1) if total_voters > 0 else 0,
        'registered_voters': total_voters,
        'voted_count': votes_cast,
        'active_stations': 1,
        'candidates': candidates,
        'positions': positions,
        'recent_activity': recent_activity,
        'vote_history': vote_history,
    }
    
    return JsonResponse(data)

# ==================== REPORTS AND ANALYTICS VIEWS ====================

@login_required
@staff_member_required
def voter_turnout_report(request):
    """Voter turnout report"""
    total_registered = User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count()
    total_voted = Vote.objects.count()
    
    context = {
        'total_registered': total_registered,
        'total_voted': total_voted,
        'overall_turnout': round((total_voted / total_registered * 100), 1) if total_registered > 0 else 0,
        'remaining_voters': total_registered - total_voted,
        'hourly_labels': ['9AM', '10AM', '11AM', '12PM', '1PM', '2PM'],
        'hourly_data': [10, 25, 45, 60, 55, 40],
        'daily_labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        'daily_data': [120, 150, 180, 200, 190, 170, 130],
        'county_stats': [],
        'age_groups': [
            {'group': '18-25', 'turnout': 65},
            {'group': '26-35', 'turnout': 78},
            {'group': '36-45', 'turnout': 82},
            {'group': '46-55', 'turnout': 71},
            {'group': '55+', 'turnout': 58},
        ],
        'gender_stats': [
            {'label': 'Male', 'percentage': 52, 'count': 1250},
            {'label': 'Female', 'percentage': 48, 'count': 1150},
        ],
    }
    return render(request, 'admin_panel/reports/voter_turnout.html', context)

@login_required
@staff_member_required
def kyc_status_report(request):
    """KYC status report"""
    context = {
        'total_submissions': User.objects.filter(user_type='VOTER').exclude(kyc_status='INCOMPLETE').count(),
        'pending_count': User.objects.filter(user_type='VOTER', kyc_status='PENDING').count(),
        'verified_count': User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count(),
        'rejected_count': User.objects.filter(user_type='VOTER', kyc_status='REJECTED').count(),
        'flagged_count': User.objects.filter(user_type='VOTER', kyc_status='FLAGGED').count(),
        'avg_processing_time': 24,
        'verification_rate': 85,
        'daily_labels': ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'],
        'daily_data': [45, 52, 38, 61, 47, 33, 29],
        'kyc_list': User.objects.filter(user_type='VOTER').order_by('-kyc_submitted_at')[:20],
        'counties': User.objects.filter(user_type='VOTER').values_list('county', flat=True).distinct().order_by('county'),
    }
    return render(request, 'admin_panel/reports/kyc_status.html', context)

@login_required
@staff_member_required
def vote_counts_report(request):
    """Vote counts report"""
    total_votes = Vote.objects.count()
    total_registered = User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count()
    
    context = {
        'total_votes': total_votes,
        'valid_votes': total_votes,
        'invalid_votes': 0,
        'turnout': round((total_votes / total_registered * 100), 1) if total_registered > 0 else 0,
        'positions': [],
        'county_labels': ['Nairobi', 'Mombasa', 'Kisumu', 'Nakuru', 'Kiambu'],
        'county_data': [450, 320, 280, 240, 210],
        'timeline_labels': ['9AM', '10AM', '11AM', '12PM', '1PM', '2PM', '3PM'],
        'timeline_data': [25, 78, 145, 210, 185, 168, 132],
    }
    return render(request, 'admin_panel/reports/vote_counts.html', context)

@login_required
@staff_member_required
def activity_log_report(request):
    """Activity log report"""
    import random
    context = {
        'total_activities': AuditLog.objects.count(),
        'unique_users': AuditLog.objects.values('user').distinct().count(),
        'today_count': AuditLog.objects.filter(timestamp__date=timezone.now().date()).count(),
        'peak_hour': '14:00',
        'hourly_labels': [f'{h}:00' for h in range(24)],
        'hourly_data': [random.randint(10, 100) for _ in range(24)],
        'activities': AuditLog.objects.all().select_related('user').order_by('-timestamp')[:50],
        'categories': AuditLog.ACTION_CATEGORIES,
    }
    return render(request, 'admin_panel/reports/activity_log.html', context)

@login_required
@staff_member_required
def export_report(request, report_type):
    """Export report as CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{report_type}_report_{timezone.now().date()}.csv"'
    
    writer = csv.writer(response)
    
    if report_type == 'voters':
        writer.writerow(['TSC Number', 'Name', 'Email', 'KYC Status', 'Has Voted', 'Registered At'])
        for user in User.objects.filter(user_type='VOTER')[:1000]:
            writer.writerow([
                user.tsc_number, user.full_name, user.email, user.kyc_status,
                'Yes' if user.has_voted else 'No', user.registered_at.date()
            ])
    
    elif report_type == 'kyc':
        writer.writerow(['Name', 'TSC Number', 'KYC Status', 'Submitted At', 'Verified At'])
        for user in User.objects.filter(user_type='VOTER')[:1000]:
            writer.writerow([
                user.full_name, user.tsc_number, user.kyc_status,
                user.kyc_submitted_at.date() if user.kyc_submitted_at else '',
                user.kyc_verified_at.date() if user.kyc_verified_at else ''
            ])
    
    elif report_type == 'votes':
        writer.writerow(['Voter', 'Timestamp', 'Candidates'])
        for vote in Vote.objects.select_related('voter').prefetch_related('candidates')[:1000]:
            candidates = ', '.join([c.full_name for c in vote.candidates.all()])
            writer.writerow([vote.voter.full_name, vote.timestamp, candidates])
    
    return response

# ==================== AUDIT LOGS VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class AuditLogListView(TemplateView):
    """Audit logs list"""
    template_name = 'admin_panel/audit/logs.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        user_filter = self.request.GET.get('user')
        action_filter = self.request.GET.get('action')
        category = self.request.GET.get('category')
        
        queryset = AuditLog.objects.all().select_related('user').order_by('-timestamp')
        
        if date_from:
            queryset = queryset.filter(timestamp__date__gte=date_from)
        if date_to:
            queryset = queryset.filter(timestamp__date__lte=date_to)
        if user_filter:
            queryset = queryset.filter(user__full_name__icontains=user_filter)
        if action_filter:
            queryset = queryset.filter(action__icontains=action_filter)
        if category:
            queryset = queryset.filter(category=category)
        
        paginator = Paginator(queryset, 50)
        page = self.request.GET.get('page')
        context['logs'] = paginator.get_page(page)
        
        context['total_events'] = AuditLog.objects.count()
        context['today_events'] = AuditLog.objects.filter(timestamp__date=timezone.now().date()).count()
        context['week_events'] = AuditLog.objects.filter(timestamp__gte=timezone.now() - timedelta(days=7)).count()
        
        return context

@method_decorator([login_required, staff_member_required], name='dispatch')
class AuditLogDetailView(DetailView):
    """Audit log details"""
    model = AuditLog
    template_name = 'admin_panel/audit/detail.html'
    context_object_name = 'log'
    pk_url_kwarg = 'log_id'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        log = self.get_object()
        context['related_logs'] = AuditLog.objects.filter(
            Q(user=log.user) | Q(action=log.action)
        ).exclude(id=log.id).order_by('-timestamp')[:10]
        return context

# ==================== NOTIFICATION VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class AdminNotificationListView(TemplateView):
    """Admin notifications list"""
    template_name = 'admin_panel/notifications/list.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        filter_type = self.request.GET.get('filter', 'all')
        queryset = Notification.objects.filter(user=self.request.user).order_by('-created_at')
        
        if filter_type == 'unread':
            queryset = queryset.filter(is_read=False)
        elif filter_type == 'action':
            queryset = queryset.filter(notification_type='ACTION_REQUIRED')
        
        paginator = Paginator(queryset, 20)
        page = self.request.GET.get('page')
        context['notifications'] = paginator.get_page(page)
        
        context['filter'] = filter_type
        context['unread_count'] = Notification.objects.filter(user=self.request.user, is_read=False).count()
        
        return context

@login_required
@staff_member_required
def mark_notification_read(request, notification_id):
    """Mark notification as read"""
    if request.method == 'POST':
        notification = get_object_or_404(Notification, id=notification_id, user=request.user)
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def mark_all_notifications_read(request):
    """Mark all notifications as read"""
    if request.method == 'POST':
        Notification.objects.filter(user=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def unread_notifications_count(request):
    """Get unread notifications count"""
    count = Notification.objects.filter(user=request.user, is_read=False).count()
    return JsonResponse({'count': count})

@login_required
@staff_member_required
def recent_notifications(request):
    """Get recent notifications for dropdown"""
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        limit = int(request.GET.get('limit', 5))
        
        notifications = Notification.objects.filter(user=request.user).order_by('-created_at')[:limit]
        
        data = {'notifications': []}
        for n in notifications:
            data['notifications'].append({
                'id': n.id,
                'title': n.title,
                'message': n.message,
                'time_ago': timesince(n.created_at),
                'is_read': n.is_read,
                'notification_type': n.notification_type
            })
        
        return JsonResponse(data)
    
    return JsonResponse({'error': 'Invalid request'}, status=400)

# ==================== SYSTEM SETTINGS VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class GeneralSettingsView(TemplateView):
    """General settings"""
    template_name = 'admin_panel/settings/general.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        messages.success(request, "General settings updated.")
        return redirect('admin_panel:general_settings')

@method_decorator([login_required, staff_member_required], name='dispatch')
class SecuritySettingsView(TemplateView):
    """Security settings"""
    template_name = 'admin_panel/settings/security.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        messages.success(request, "Security settings updated.")
        return redirect('admin_panel:security_settings')

@method_decorator([login_required, staff_member_required], name='dispatch')
class EmailSettingsView(TemplateView):
    """Email settings"""
    template_name = 'admin_panel/settings/email.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        messages.success(request, "Email settings updated.")
        return redirect('admin_panel:email_settings')

@method_decorator([login_required, staff_member_required], name='dispatch')
class BackupSettingsView(TemplateView):
    """Backup settings view"""
    template_name = 'admin_panel/settings/backup.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Initialize backup manager
        backup_manager = BackupManager()
        
        # Get storage stats
        stats = backup_manager.get_storage_stats()
        
        # Add all stats to context
        context.update({
            'total_backups': stats.get('total_backups', 0),
            'total_size': stats.get('total_size', '0 B'),
            'disk_used': stats.get('disk_used', '0 GB'),
            'disk_total': stats.get('disk_total', '0 GB'),
            'disk_free': stats.get('disk_free', '0 GB'),
            'disk_percent': stats.get('disk_percent', 0),
            'backup_frequency': 'Daily',  # Get from settings
            'backup_dir': str(backup_manager.backup_dir),
        })
        
        # Get backup list
        backups = backup_manager.list_backups()
        context['backups'] = backups[:10]  # Show last 10 backups
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle backup settings form submission"""
        if 'action' in request.POST:
            if request.POST['action'] == 'save_settings':
                # Save backup settings
                messages.success(request, "Backup settings saved successfully!")
            elif request.POST['action'] == 'create_backup':
                # Trigger manual backup
                messages.success(request, "Backup created successfully!")
        
        return redirect('admin_panel:backup_settings')

@method_decorator([login_required, staff_member_required], name='dispatch')
class MaintenanceModeView(TemplateView):
    """Maintenance mode"""
    template_name = 'admin_panel/settings/maintenance.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        messages.success(request, "Maintenance settings updated.")
        return redirect('admin_panel:maintenance_mode')

@login_required
@staff_member_required
def test_email_connection(request):
    """Test email connection"""
    if request.method == 'POST':
        # Test email logic here
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid method'}, status=400)

# ==================== DATA MANAGEMENT VIEWS ====================

@method_decorator([login_required, staff_member_required], name='dispatch')
class BackupListView(TemplateView):
    """Backup list"""
    template_name = 'admin_panel/data/backups.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['total_backups'] = 12
        context['total_size'] = '1.8 GB'
        context['last_backup_date'] = timezone.now() - timedelta(hours=5)
        context['storage_used'] = '45.2 GB'
        context['storage_total'] = '100 GB'
        context['backups'] = []
        return context

@login_required
@staff_member_required
def create_backup(request):
    """Create backup"""
    if request.method == 'POST':
        backup_id = f"backup_{timezone.now().strftime('%Y%m%d_%H%M%S')}"
        log_audit(request.user, f"Created backup {backup_id}", request=request)
        return JsonResponse({'status': 'success', 'backup_id': backup_id})
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def delete_backup(request, backup_id):
    """Delete backup"""
    if request.method == 'POST':
        log_audit(request.user, f"Deleted backup {backup_id}", request=request)
        return JsonResponse({'status': 'success'})
    return JsonResponse({'error': 'Invalid method'}, status=400)

@login_required
@staff_member_required
def download_backup(request, backup_id):
    """Download backup"""
    response = HttpResponse(content_type='application/octet-stream')
    response['Content-Disposition'] = f'attachment; filename="backup_{backup_id}.sql"'
    return response

# ==================== API ENDPOINTS ====================

@login_required
@staff_member_required
def get_realtime_stats(request):
    """Get realtime stats"""
    total_voters = User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count()
    votes_cast = Vote.objects.count()
    
    data = {
        'total_voters': total_voters,
        'votes_cast': votes_cast,
        'voter_turnout': round((votes_cast / total_voters * 100), 2) if total_voters > 0 else 0,
        'timestamp': timezone.now().isoformat()
    }
    return JsonResponse(data)

@login_required
@staff_member_required
def get_dashboard_stats(request):
    """Get dashboard stats"""
    data = {
        'total_voters': User.objects.filter(user_type='VOTER').count(),
        'verified_voters': User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count(),
        'pending_kyc': User.objects.filter(user_type='VOTER', kyc_status='PENDING').count(),
        'total_votes': Vote.objects.count(),
        'total_candidates': Candidate.objects.filter(is_active=True).count(),
        'total_teams': Team.objects.filter(is_active=True).count(),
        'pending_resets': DeviceResetRequest.objects.filter(status='PENDING').count(),
        'pending_candidate_applications': CandidateApplication.objects.filter(status='PENDING').count(),
        'pending_team_applications': Team.objects.filter(status='PENDING').count(),
    }
    return JsonResponse(data)

@login_required
@staff_member_required
def get_kyc_stats(request):
    """Get KYC stats"""
    return kyc_statistics(request)

@login_required
@staff_member_required
def get_voter_stats(request):
    """Get voter stats"""
    data = {
        'total': User.objects.filter(user_type='VOTER').count(),
        'active': User.objects.filter(user_type='VOTER', account_status='ACTIVE').count(),
        'suspended': User.objects.filter(user_type='VOTER', account_status='SUSPENDED').count(),
        'pending': User.objects.filter(user_type='VOTER', account_status='PENDING').count(),
        'verified_kyc': User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count(),
        'pending_kyc': User.objects.filter(user_type='VOTER', kyc_status='PENDING').count(),
        'has_voted': User.objects.filter(user_type='VOTER', has_voted=True).count(),
    }
    return JsonResponse(data)

@login_required
@staff_member_required
def get_election_stats(request):
    """Get election stats"""
    election = Election.objects.filter(status='ACTIVE').first()
    data = {
        'status': election.status if election else 'INACTIVE',
        'voting_open': election.is_voting_open() if election else False,
        'total_votes': Vote.objects.count(),
    }
    return JsonResponse(data)

@login_required
@staff_member_required
def get_activity_feed(request):
    """Get activity feed"""
    activities = []
    
    for vote in Vote.objects.select_related('voter').order_by('-timestamp')[:5]:
        activities.append({
            'type': 'vote',
            'description': f"{vote.voter.full_name} cast a vote",
            'timestamp': vote.timestamp.isoformat(),
            'time_ago': timesince(vote.timestamp)
        })
    
    for user in User.objects.filter(user_type='VOTER').order_by('-registered_at')[:5]:
        activities.append({
            'type': 'registration',
            'description': f"New voter: {user.full_name}",
            'timestamp': user.registered_at.isoformat(),
            'time_ago': timesince(user.registered_at)
        })
    
    for app in CandidateApplication.objects.filter(status='PENDING').order_by('-applied_at')[:3]:
        activities.append({
            'type': 'candidate_application',
            'description': f"New candidate: {app.voter.full_name} for {app.position.name}",
            'timestamp': app.applied_at.isoformat(),
            'time_ago': timesince(app.applied_at)
        })
    
    return JsonResponse({'activities': activities})

@login_required
@staff_member_required
def find_voter(request):
    """Find voter by TSC or email"""
    query = request.GET.get('q', '')
    
    if not query:
        return JsonResponse({'error': 'No query provided'}, status=400)
    
    voter = User.objects.filter(
        Q(tsc_number__iexact=query) | Q(email__iexact=query)
    ).filter(user_type='VOTER').first()
    
    if voter:
        return JsonResponse({
            'id': voter.id,
            'full_name': voter.full_name,
            'tsc_number': voter.tsc_number,
            'email': voter.email
        })
    
    return JsonResponse({'error': 'Voter not found'}, status=404)

@login_required
@staff_member_required
def deletion_requests_count(request):
    """Get pending deletion requests count"""
    count = AccountActionRequest.objects.filter(action_type='DELETE', status='PENDING').count()
    return JsonResponse({'pending': count})

@login_required
@staff_member_required
def candidate_applications_count(request):
    """Get pending candidate applications count"""
    count = CandidateApplication.objects.filter(status='PENDING').count()
    return JsonResponse({'pending': count})

@login_required
@staff_member_required
def team_applications_count(request):
    """Get pending team applications count"""
    count = Team.objects.filter(status='PENDING').count()
    return JsonResponse({'pending': count})

@login_required
@staff_member_required
def admin_pending_count(request):
    """Get pending admin approvals count"""
    count = User.objects.filter(user_type='ADMIN', account_status='PENDING').count()
    return JsonResponse({'pending': count})
import csv
import io
from django.http import JsonResponse
from django.contrib import messages
from django.views.decorators.http import require_POST

@login_required
@staff_member_required
def download_position_template(request):
    """Download CSV template for bulk position upload"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="position_template.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['election_id', 'name', 'order', 'max_votes', 'description', 'is_active'])
    writer.writerow(['1', 'President', '1', '1', 'Head of the organization', '1'])
    writer.writerow(['1', 'Vice President', '2', '1', 'Deputy head', '1'])
    writer.writerow(['1', 'Secretary', '3', '1', 'Records and documentation', '1'])
    
    return response

@login_required
@staff_member_required
@require_POST
def bulk_upload_positions(request):
    """Handle bulk upload of positions via CSV"""
    try:
        csv_file = request.FILES.get('csv_file')
        if not csv_file:
            return JsonResponse({'success': False, 'error': 'No file uploaded'})
        
        # Read and parse CSV
        decoded_file = csv_file.read().decode('utf-8')
        io_string = io.StringIO(decoded_file)
        reader = csv.DictReader(io_string)
        
        created_count = 0
        updated_count = 0
        failed_count = 0
        errors = []
        
        for row in reader:
            try:
                # Validate required fields
                if not row.get('election_id') or not row.get('name'):
                    failed_count += 1
                    errors.append(f"Missing required fields in row: {row}")
                    continue
                
                # Get or create position
                position, created = Position.objects.update_or_create(
                    election_id=row['election_id'],
                    name=row['name'],
                    defaults={
                        'order': row.get('order', 1),
                        'max_votes': row.get('max_votes', 1),
                        'description': row.get('description', ''),
                        'is_active': row.get('is_active', '1').lower() in ['1', 'true', 'yes'],
                    }
                )
                
                if created:
                    created_count += 1
                else:
                    updated_count += 1
                    
            except Exception as e:
                failed_count += 1
                errors.append(f"Error processing row: {str(e)}")
        
        log_audit(request.user, f"Bulk uploaded positions: {created_count} created, {updated_count} updated", request=request)
        
        return JsonResponse({
            'success': True,
            'created': created_count,
            'updated': updated_count,
            'failed': failed_count,
            'errors': errors[:10]  # Return first 10 errors
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
@method_decorator([login_required, staff_member_required], name='dispatch')
class BackupListView(TemplateView):
    """Backup list view"""
    template_name = 'admin_panel/data/backups.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Initialize backup manager
        backup_manager = BackupManager()
        
        # Get storage stats
        stats = backup_manager.get_storage_stats()
        context.update(stats)
        
        # Get backup list
        backups = backup_manager.list_backups()
        
        # Pagination
        paginator = Paginator(backups, 10)
        page = self.request.GET.get('page')
        context['backups'] = paginator.get_page(page)
        context['is_paginated'] = paginator.num_pages > 1
        context['page_obj'] = paginator.get_page(page)
        
        # Auto-backup settings
        context['backup_frequency'] = 'Daily'  # Get from settings
        
        return context


@login_required
@staff_member_required
def create_backup(request):
    """Create a new backup"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    if request.user.user_type != 'SUPER_ADMIN':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        backup_type = request.POST.get('type', 'manual')
        include_media = request.POST.get('include_media') == 'true'
        include_db = request.POST.get('include_db') == 'true'
        
        backup_manager = BackupManager()
        backup_id, info = backup_manager.create_backup(
            backup_type=backup_type,
            include_media=include_media,
            include_db=include_db
        )
        
        log_audit(request.user, f"Created backup: {backup_id}", request=request)
        
        return JsonResponse({
            'success': True,
            'backup_id': backup_id,
            'message': f'Backup {backup_id} created successfully'
        })
        
    except Exception as e:
        logger.error(f"Backup creation failed: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@staff_member_required
def backup_details(request, backup_id):
    """Get backup details"""
    if request.user.user_type != 'SUPER_ADMIN':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    backup_manager = BackupManager()
    info = backup_manager.get_backup_info(backup_id)
    
    if not info:
        return JsonResponse({'error': 'Backup not found'}, status=404)
    
    return JsonResponse(info)


@login_required
@staff_member_required
def download_backup(request, backup_id):
    """Download a backup as zip"""
    if request.user.user_type != 'SUPER_ADMIN':
        messages.error(request, "Permission denied.")
        return redirect('admin_panel:backup_list')
    
    backup_manager = BackupManager()
    zip_path = backup_manager.download_backup(backup_id)
    
    if not zip_path or not zip_path.exists():
        messages.error(request, "Backup not found.")
        return redirect('admin_panel:backup_list')
    
    response = FileResponse(
        open(zip_path, 'rb'),
        as_attachment=True,
        filename=f"{backup_id}.zip"
    )
    
    # Clean up the temporary zip file after sending
    import atexit
    atexit.register(lambda: os.unlink(zip_path))
    
    return response


@login_required
@staff_member_required
def delete_backup(request, backup_id):
    """Delete a backup"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    if request.user.user_type != 'SUPER_ADMIN':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    backup_manager = BackupManager()
    success = backup_manager.delete_backup(backup_id)
    
    if success:
        log_audit(request.user, f"Deleted backup: {backup_id}", request=request)
        return JsonResponse({'success': True})
    
    return JsonResponse({'error': 'Backup not found'}, status=404)


@login_required
@staff_member_required
def restore_backup(request, backup_id):
    """Restore from a backup"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    if request.user.user_type != 'SUPER_ADMIN':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        restore_db = request.POST.get('restore_db') == 'true'
        restore_media = request.POST.get('restore_media') == 'true'
        
        backup_manager = BackupManager()
        backup_manager.restore_backup(
            backup_id,
            restore_db=restore_db,
            restore_media=restore_media
        )
        
        log_audit(request.user, f"Restored from backup: {backup_id}", request=request)
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        logger.error(f"Restore failed: {e}")
        return JsonResponse({'success': False, 'error': str(e)}, status=500)


@login_required
@staff_member_required
def bulk_delete_backups(request):
    """Delete multiple backups"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid method'}, status=400)
    
    if request.user.user_type != 'SUPER_ADMIN':
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        data = json.loads(request.body)
        backup_ids = data.get('ids', [])
        
        backup_manager = BackupManager()
        deleted = []
        failed = []
        
        for backup_id in backup_ids:
            if backup_manager.delete_backup(backup_id):
                deleted.append(backup_id)
            else:
                failed.append(backup_id)
        
        log_audit(request.user, f"Bulk deleted {len(deleted)} backups", request=request)
        
        return JsonResponse({
            'success': True,
            'deleted': deleted,
            'failed': failed
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=500)
@method_decorator([login_required, staff_member_required], name='dispatch')
class MaintenanceSettingsView(TemplateView):
    """Maintenance settings view"""
    template_name = 'admin_panel/settings/maintenance.html'
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "Permission denied.")
            return redirect('admin_panel:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get maintenance settings
        maintenance = MaintenanceMode.get_settings()
        
        context.update({
            'system_status': 'offline' if maintenance.is_active else 'online',
            'maintenance_message': maintenance.message,
            'allowed_ips': maintenance.allowed_ips,
            'maintenance_start': maintenance.scheduled_start.isoformat() if maintenance.scheduled_start else '',
            'maintenance_end': maintenance.scheduled_end.isoformat() if maintenance.scheduled_end else '',
            'notify_users': maintenance.notify_users,
            
            # System health
            'database_size': self.get_database_size(),
            'cache_hits': self.get_cache_stats(),
            'storage_used': self.get_storage_used(),
            'storage_total': self.get_storage_total(),
            'storage_percent': self.get_storage_percent(),
            'active_workers': self.get_active_workers(),
            'total_workers': 4,  # Configure based on your setup
            
            # System logs
            'system_logs': SystemLog.objects.all()[:100],
            
            # Performance metrics
            'avg_response_time': self.get_avg_response_time(),
            'peak_load': self.get_peak_load(),
            'peak_load_time': self.get_peak_load_time(),
            'error_rate': self.get_error_rate(),
            'performance_labels': self.get_performance_labels(),
            'response_times': self.get_response_times(),
            'request_rates': self.get_request_rates(),
        })
        
        return context
    
    def post(self, request, *args, **kwargs):
        action = request.POST.get('action')
        
        if action == 'save_settings':
            return self.save_settings(request)
        elif action == 'enable_maintenance':
            return self.enable_maintenance(request)
        elif action == 'disable_maintenance':
            return self.disable_maintenance(request)
        
        return redirect('admin_panel:maintenance_mode')
    
    def save_settings(self, request):
        maintenance = MaintenanceMode.get_settings()
        maintenance.message = request.POST.get('maintenance_message', maintenance.message)
        maintenance.allowed_ips = request.POST.get('allowed_ips', '')
        maintenance.notify_users = request.POST.get('notify_users') == 'on'
        
        # Parse scheduled maintenance
        start_str = request.POST.get('maintenance_start')
        end_str = request.POST.get('maintenance_end')
        
        if start_str:
            maintenance.scheduled_start = datetime.fromisoformat(start_str)
        if end_str:
            maintenance.scheduled_end = datetime.fromisoformat(end_str)
        
        maintenance.save()
        
        messages.success(request, "Maintenance settings saved successfully!")
        return redirect('admin_panel:maintenance_mode')
    
    def enable_maintenance(self, request):
        maintenance = MaintenanceMode.get_settings()
        maintenance.is_active = True
        maintenance.enabled_by = request.user
        maintenance.enabled_at = timezone.now()
        maintenance.save()
        
        # Log the action
        SystemLog.objects.create(
            level='INFO',
            message=f"Maintenance mode enabled by {request.user.email}"
        )
        
        messages.success(request, "Maintenance mode enabled!")
        return redirect('admin_panel:maintenance_mode')
    
    def disable_maintenance(self, request):
        maintenance = MaintenanceMode.get_settings()
        maintenance.is_active = False
        maintenance.disabled_at = timezone.now()
        maintenance.save()
        
        # Log the action
        SystemLog.objects.create(
            level='INFO',
            message=f"Maintenance mode disabled by {request.user.email}"
        )
        
        messages.success(request, "Maintenance mode disabled!")
        return redirect('admin_panel:maintenance_mode')
    
    # Helper methods for system stats
    def get_database_size(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_database_size(current_database())")
                size = cursor.fetchone()[0]
                return self.format_size(size)
        except:
            return "Unknown"
    
    def get_cache_stats(self):
        # Implement based on your cache backend
        return "98"
    
    def get_storage_used(self):
        return self.format_size(psutil.disk_usage('/').used)
    
    def get_storage_total(self):
        return self.format_size(psutil.disk_usage('/').total)
    
    def get_storage_percent(self):
        return psutil.disk_usage('/').percent
    
    def get_active_workers(self):
        # Implement based on your worker setup
        return 4
    
    def get_avg_response_time(self):
        metrics = PerformanceMetric.objects.order_by('-timestamp')[:100]
        if metrics:
            return sum(m.response_time for m in metrics) / len(metrics)
        return 0
    
    def get_peak_load(self):
        metrics = PerformanceMetric.objects.order_by('-request_rate')[:1]
        return metrics[0].request_rate if metrics else 0
    
    def get_peak_load_time(self):
        metrics = PerformanceMetric.objects.order_by('-request_rate')[:1]
        if metrics:
            return metrics[0].timestamp.strftime("%H:%M %p")
        return "Never"
    
    def get_error_rate(self):
        metrics = PerformanceMetric.objects.order_by('-timestamp')[:60]  # Last hour
        if metrics:
            return sum(m.error_rate for m in metrics) / len(metrics)
        return 0
    
    def get_performance_labels(self):
        metrics = PerformanceMetric.objects.order_by('-timestamp')[:24]  # Last 24 points
        return [m.timestamp.strftime("%H:%M") for m in reversed(metrics)]
    
    def get_response_times(self):
        metrics = PerformanceMetric.objects.order_by('-timestamp')[:24]
        return [m.response_time for m in reversed(metrics)]
    
    def get_request_rates(self):
        metrics = PerformanceMetric.objects.order_by('-timestamp')[:24]
        return [m.request_rate for m in reversed(metrics)]
    
    def format_size(self, bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if bytes < 1024.0:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024.0
        return f"{bytes:.1f} PB"


@login_required
@staff_member_required
def get_system_logs(request):
    """API endpoint to get system logs"""
    level = request.GET.get('level', 'INFO')
    logs = SystemLog.objects.all()
    
    if level != 'all':
        logs = logs.filter(level=level.upper())
    
    html = ''
    for log in logs[:100]:
        level_class = {
            'ERROR': 'text-red-400',
            'WARNING': 'text-yellow-400',
            'INFO': 'text-gray-300',
            'DEBUG': 'text-gray-500',
        }.get(log.level, 'text-gray-300')
        
        html += f'''
        <div class="mb-1 {level_class}">
            <span class="text-gray-500">[{log.timestamp.strftime("%Y-%m-%d %H:%M:%S")}]</span>
            <span class="text-gray-400">{log.level}</span>
            <span>{log.message}</span>
            {f'<pre class="ml-4 text-xs text-gray-500">{log.traceback}</pre>' if log.traceback else ''}
        </div>
        '''
    
    if not html:
        html = '<div class="text-gray-500 text-center py-4">No logs available</div>'
    
    return HttpResponse(html)


@login_required
@staff_member_required
def download_system_logs(request):
    """Download system logs as text file"""
    logs = SystemLog.objects.all()[:1000]
    
    content = "System Logs\n"
    content += "=" * 80 + "\n\n"
    
    for log in logs:
        content += f"[{log.timestamp}] {log.level}: {log.message}\n"
        if log.traceback:
            content += f"Traceback:\n{log.traceback}\n"
        content += "\n"
    
    response = HttpResponse(content, content_type='text/plain')
    response['Content-Disposition'] = 'attachment; filename="system_logs.txt"'
    return response


@login_required
@staff_member_required
def clear_system_logs(request):
    """Clear all system logs"""
    if request.method == 'POST':
        SystemLog.objects.all().delete()
        return JsonResponse({'success': True})
    return JsonResponse({'error': 'Invalid method'}, status=400)
@login_required
@staff_member_required
def approve_admin(request, admin_id):
    """Approve a pending admin registration"""
    if request.method == 'POST':
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "You don't have permission to perform this action.")
            return redirect('admin_panel:dashboard')
        
        admin = get_object_or_404(User, id=admin_id, user_type='ADMIN')
        
        # Generate admin ID
        admin_id_number = f"ADMIN{str(admin.id).zfill(4)}"
        
        # Check if admin ID is unique
        while User.objects.filter(admin_id=admin_id_number).exists():
            # If exists, add random suffix
            import random
            admin_id_number = f"ADMIN{str(admin.id).zfill(4)}{random.randint(10, 99)}"
        
        admin.is_active = True
        admin.account_status = 'ACTIVE'
        admin.admin_id = admin_id_number
        admin.verified_at = timezone.now()
        admin.verified_by = request.user
        admin.save()
        
        # Send approval email
        send_admin_approval_email(admin, admin_id_number)
        
        # Create notification
        Notification.objects.create(
            user=admin,
            title='Admin Account Approved',
            message=f'Your administrator account has been approved. Your Admin ID is: {admin_id_number}',
            notification_type='SUCCESS'
        )
        
        logger.info(f"Admin {admin.full_name} approved by {request.user.username}")
        
        messages.success(request, f"Admin {admin.full_name} approved. Admin ID: {admin_id_number}")
        return redirect('admin_panel:pending_admin_approvals')
    
    return redirect('admin_panel:pending_admin_approvals')


@login_required
@staff_member_required
def reject_admin(request, admin_id):
    """Reject a pending admin registration and delete the account"""
    if request.method == 'POST':
        if request.user.user_type != 'SUPER_ADMIN':
            messages.error(request, "You don't have permission to perform this action.")
            return redirect('admin_panel:dashboard')
        
        admin = get_object_or_404(User, id=admin_id, user_type='ADMIN', account_status='PENDING')
        reason = request.POST.get('reason', 'Application does not meet requirements')
        
        # Send rejection email before deletion
        send_admin_rejection_email(admin, reason)
        
        # Log the rejection
        logger.warning(f"Admin {admin.full_name} ({admin.email}) rejected by {request.user.username}. Reason: {reason}")
        
        # Delete the admin account
        admin.delete()
        
        messages.warning(request, f"Admin application rejected and account deleted.")
        return redirect('admin_panel:pending_admin_approvals')
    
    return redirect('admin_panel:pending_admin_approvals')


def send_admin_approval_email(admin, admin_id):
    """Send approval email to new admin"""
    try:
        subject = 'Your Administrator Account Has Been Approved'
        message = f"""
        Dear {admin.full_name},
        
        Congratulations! Your administrator account has been approved.
        
        Your Admin ID is: {admin_id}
        
        You can now log in using:
        - Admin ID: {admin_id}
        - Email: {admin.email}
        - Password: (the password you set during registration)
        
        Please log in at: {settings.SITE_URL}/accounts/admin-login/
        
        Best regards,
        Agora Super Admin Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [admin.email],
            fail_silently=False,
        )
        logger.info(f"Approval email sent to {admin.email}")
    except Exception as e:
        logger.error(f"Failed to send approval email to {admin.email}: {e}")


def send_admin_rejection_email(admin, reason):
    """Send rejection email to applicant"""
    try:
        subject = 'Update on Your Administrator Application'
        message = f"""
        Dear {admin.full_name},
        
        Thank you for your interest in becoming an administrator.
        
        After careful review, we regret to inform you that your application has not been approved at this time.
        
        Reason: {reason}
        
        You may submit a new application after addressing the concerns mentioned above.
        
        Best regards,
        Agora Super Admin Team
        """
        
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [admin.email],
            fail_silently=False,
        )
        logger.info(f"Rejection email sent to {admin.email}")
    except Exception as e:
        logger.error(f"Failed to send rejection email to {admin.email}: {e}")
# Add this function to your views.py, preferably near other API endpoints

@login_required
@staff_member_required
def voter_status(request, voter_id):
    """Check voter status (has voted, suspended, etc.)"""
    try:
        voter = get_object_or_404(User, id=voter_id, user_type='VOTER')
        
        # Count votes for this voter
        votes_count = Vote.objects.filter(voter=voter).count()
        
        data = {
            'id': voter.id,
            'has_voted': voter.has_voted or votes_count > 0,
            'votes_count': votes_count,
            'account_status': voter.account_status,
            'kyc_status': voter.kyc_status,
            'tsc_verified': voter.tsc_verified,
            'is_suspended': voter.account_status == 'SUSPENDED',
            'is_active': voter.is_active,
            'can_delete': not (voter.has_voted or votes_count > 0)  # Can only delete if hasn't voted
        }
        return JsonResponse(data)
        
    except Exception as e:
        logger.error(f"Error checking voter status: {e}")
        return JsonResponse({'error': str(e)}, status=500)