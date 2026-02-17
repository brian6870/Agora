from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.generic import TemplateView, ListView, DetailView, CreateView, UpdateView, DeleteView, FormView
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.db.models import Count, Q, Sum
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from django.db import transaction
from django.core.cache import cache
import json
import hashlib
import uuid
import logging
from datetime import datetime

from apps.accounts.models import User
from apps.voting.models import (
    Candidate, Position, Team, Vote, Election, 
    CandidateApplication, VoteAuditLog
)
from apps.voting.forms import (
    CandidateApplicationForm, TeamForm, VoteForm
)
from apps.core.models import ElectionSettings, DeviceResetRequest

logger = logging.getLogger(__name__)

# Custom rate limiting function
def check_rate_limit(request, key='ip', limit=5, period=60):
    """Simple rate limiting function"""
    from django.core.cache import cache
    
    if key == 'ip':
        client_id = get_client_ip(request)
    else:
        client_id = request.POST.get(key, request.GET.get(key, ''))
    
    cache_key = f"rate_limit_{key}_{client_id}"
    attempts = cache.get(cache_key, 0)
    
    if attempts >= limit:
        return False
    
    cache.set(cache_key, attempts + 1, period)
    return True

def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR', '')

# ==================== VOTER VIEWS ====================

@method_decorator([login_required, never_cache], name='dispatch')
class VoterDashboardView(TemplateView):
    """Main dashboard for voters"""
    template_name = 'voter/dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Get active election - IMPORTANT: Filter by status='ACTIVE'
        try:
            # This gets the election that is currently active
            context['election'] = Election.objects.filter(status='ACTIVE').first()
            
            # For debugging - remove in production
            if context['election']:
                print(f"Active election found: {context['election'].name}")
                print(f"Election status: {context['election'].status}")
                print(f"Allow voting: {context['election'].allow_voting}")
                print(f"Emergency pause: {context['election'].emergency_pause}")
                print(f"Voting open: {context['election'].is_voting_open()}")
            else:
                print("No active election found")
                
        except Exception as e:
            print(f"Error fetching election: {e}")
            context['election'] = None
        
        # Statistics
        context['total_voters'] = User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count()
        context['verified_voters'] = User.objects.filter(user_type='VOTER', kyc_status='VERIFIED').count()
        context['votes_cast'] = Vote.objects.count()
        context['total_candidates'] = Candidate.objects.filter(is_active=True).count()
        context['total_teams'] = Team.objects.filter(is_active=True).count()
        
        # User specific info
        context['kyc_status'] = user.get_kyc_status_display() if hasattr(user, 'get_kyc_status_display') else 'Unknown'
        context['has_voted'] = user.has_voted
        
        # Get user's applications
        context['candidate_application'] = CandidateApplication.objects.filter(
            voter=user
        ).order_by('-applied_at').first()
        
        context['team_application'] = Team.objects.filter(
            created_by=user,
            status='PENDING'
        ).order_by('-created_at').first()
        
        # Check if user is a candidate
        context['user_is_candidate'] = Candidate.objects.filter(voter=user).exists()
        
        # Get user's team
        context['user_team'] = Team.objects.filter(
            candidates__voter=user,
            is_active=True
        ).first()
        
        # Calculate voting progress
        if context['total_voters'] > 0:
            context['voting_progress'] = (context['votes_cast'] / context['total_voters']) * 100
        else:
            context['voting_progress'] = 0
        
        context['voter_turnout'] = round(context['voting_progress'], 1)
        
        # Get recent votes (last 5)
        context['recent_votes'] = Vote.objects.select_related('voter').order_by('-timestamp')[:5]
        
        return context

@method_decorator([login_required, never_cache], name='dispatch')
class VotingAreaView(TemplateView):
    """Main voting interface"""
    template_name = 'voter/voting_area.html'
    
    def dispatch(self, request, *args, **kwargs):
        user = request.user
        
        # Check if user is allowed to vote
        if user.user_type != 'VOTER':
            messages.error(request, "Only voters can access the voting area.")
            return redirect('core:dashboard')
        
        if user.kyc_status != 'VERIFIED':
            messages.error(request, f"Your KYC is {user.get_kyc_status_display()}. You cannot vote until verified.")
            return redirect('core:dashboard')
        
        if user.has_voted:
            messages.info(request, "You have already cast your vote.")
            return redirect('core:results')
        
        # Check if voting is open in active election
        try:
            election = Election.objects.filter(status='ACTIVE').first()
            if not election:
                messages.warning(request, "No active election found.")
                return redirect('core:dashboard')
            
            if not election.is_voting_open():
                if election.emergency_pause:
                    messages.warning(request, f"Voting is temporarily paused. Reason: {election.pause_reason}")
                else:
                    messages.warning(request, "Voting is currently closed.")
                return redirect('core:dashboard')
        except Exception as e:
            messages.warning(request, "Election settings not configured.")
            return redirect('core:dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get active election
        election = Election.objects.filter(status='ACTIVE').first()
        context['election'] = election
        
        if election:
            # Get all positions with their candidates
            positions = Position.objects.filter(election=election, is_active=True).order_by('order')
            ballot_data = []
            
            for position in positions:
                candidates = Candidate.objects.filter(
                    election=election,
                    position=position,
                    is_active=True
                ).select_related('team').order_by('order', 'full_name')
                
                ballot_data.append({
                    'position': position,
                    'candidates': candidates
                })
            
            context['ballot'] = ballot_data
        
        return context
    
    def post(self, request, *args, **kwargs):
        """Handle vote submission"""
        try:
            data = json.loads(request.body)
            votes = data.get('votes', {})
            
            # Validate votes
            if not votes:
                return JsonResponse({'error': 'No votes submitted'}, status=400)
            
            # Process the vote
            return self.process_vote(request, votes)
            
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid vote data'}, status=400)
    
    @transaction.atomic
    def process_vote(self, request, votes):
        """Process and record the vote"""
        user = request.user
        
        # Double-check voting eligibility
        if user.has_voted:
            return JsonResponse({'error': 'You have already voted'}, status=403)
        
        # Get active election
        election = Election.objects.filter(status='ACTIVE').first()
        if not election:
            return JsonResponse({'error': 'No active election found'}, status=403)
        
        if not election.is_voting_open():
            return JsonResponse({'error': 'Voting is closed'}, status=403)
        
        # Validate all positions are voted
        positions = Position.objects.filter(election=election, is_active=True).count()
        if len(votes) != positions:
            return JsonResponse({'error': 'Please vote for all positions'}, status=400)
        
        # Create vote record
        vote = Vote.objects.create(
            election=election,
            voter=user,
            ip_address=get_client_ip(request),
            device_fingerprint=request.session.get('device_fingerprint', ''),
            vote_token=uuid.uuid4()
        )
        
        # Add selected candidates
        candidates_voted = []
        for position_id, candidate_id in votes.items():
            try:
                candidate = Candidate.objects.get(
                    id=candidate_id,
                    election=election,
                    position_id=position_id,
                    is_active=True
                )
                vote.candidates.add(candidate)
                candidates_voted.append(candidate)
                
                # Increment candidate vote count
                candidate.vote_count += 1
                candidate.save()
                
            except Candidate.DoesNotExist:
                # Rollback transaction
                transaction.set_rollback(True)
                return JsonResponse({'error': 'Invalid candidate selection'}, status=400)
        
        # Update user voting status
        user.has_voted = True
        user.voted_at = timezone.now()
        user.save()
        
        # Update election stats
        election.total_votes_cast += 1
        election.save()
        
        # Create audit log
        VoteAuditLog.objects.create(
            election=election,
            vote=vote,
            action='VOTE_CAST',
            ip_address=get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            metadata={
                'voter_tsc': user.tsc_number,
                'voter_id': user.id,
                'candidates': [c.id for c in candidates_voted],
                'timestamp': str(timezone.now())
            }
        )
        
        logger.info(f"Vote cast by {user.tsc_number} - Token: {vote.vote_token}")
        
        return JsonResponse({
            'success': True,
            'message': 'Your vote has been recorded successfully!',
            'redirect': '/results/'
        })

@method_decorator([login_required], name='dispatch')
class ApplyCandidateView(CreateView):
    """View for voters to apply as candidates"""
    model = CandidateApplication
    form_class = CandidateApplicationForm
    template_name = 'voter/apply_candidate.html'
    success_url = reverse_lazy('core:application_status')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'VOTER':
            messages.error(request, "Only voters can apply as candidates.")
            return redirect('core:dashboard')
        
        if request.user.kyc_status != 'VERIFIED':
            messages.error(request, "You must have verified KYC to apply as a candidate.")
            return redirect('core:dashboard')
        
        # Get the election from URL or default to first active/pending
        self.election = None
        election_id = request.GET.get('election')
        if election_id:
            try:
                self.election = Election.objects.get(id=election_id)
            except Election.DoesNotExist:
                pass
        
        if not self.election:
            self.election = Election.objects.filter(status__in=['ACTIVE', 'PENDING']).first()
        
        if not self.election:
            messages.error(request, "No election available for applications.")
            return redirect('core:dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['election'] = self.election  # Pass election to form
        return kwargs
    
    def get_initial(self):
        initial = super().get_initial()
        initial['election'] = self.election.id  # Pass election ID as initial value
        
        # Pre-select position if provided
        position_id = self.request.GET.get('position')
        if position_id:
            try:
                initial['position'] = Position.objects.get(id=position_id, election=self.election)
            except Position.DoesNotExist:
                pass
        
        return initial
    
    def form_valid(self, form):
        # Ensure election is set
        if not form.instance.election_id:
            form.instance.election = self.election
        
        form.instance.voter = self.request.user
        
        # Double-check for existing application
        existing = CandidateApplication.objects.filter(
            voter=self.request.user,
            election=self.election,
            position=form.cleaned_data['position']
        ).exists()
        
        if existing:
            messages.error(self.request, "You have already applied for this position.")
            return redirect('core:application_status')
        
        messages.success(self.request, "Your candidate application has been submitted for review.")
        return super().form_valid(form)
    
    def form_invalid(self, form):
        # Log form errors for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Form errors: {form.errors}")
        
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['election'] = self.election
        
        # Only show ACTIVE positions
        context['positions'] = Position.objects.filter(
            election=self.election,
            is_active=True
        ).order_by('order')
        
        # Only show APPROVED teams
        context['teams'] = Team.objects.filter(
            election=self.election,
            status='APPROVED',
            is_active=True
        ).order_by('name')
        
        # Check if user already has an application for any position in this election
        context['existing_application'] = CandidateApplication.objects.filter(
            voter=self.request.user,
            election=self.election
        ).exists()
        
        # Pre-select values from GET parameters
        context['selected_position'] = self.request.GET.get('position')
        context['selected_team'] = self.request.GET.get('team')
        
        return context
@method_decorator([login_required], name='dispatch')
class CreateTeamView(CreateView):
    """View for voters to create teams"""
    model = Team
    form_class = TeamForm
    template_name = 'voter/create_team.html'
    success_url = reverse_lazy('core:application_status')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.user_type != 'VOTER':
            messages.error(request, "Only voters can create teams.")
            return redirect('core:dashboard')
        
        if request.user.kyc_status != 'VERIFIED':
            messages.error(request, "You must have verified KYC to create a team.")
            return redirect('core:dashboard')
        
        return super().dispatch(request, *args, **kwargs)
    
    def get_initial(self):
        initial = super().get_initial()
        # Pre-select election if provided in URL
        election_id = self.request.GET.get('election')
        if election_id:
            try:
                initial['election'] = Election.objects.get(id=election_id)
            except Election.DoesNotExist:
                pass
        return initial
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        return kwargs
    
    def form_valid(self, form):
        # Check if user already has ANY team application for this election (regardless of status)
        election = form.cleaned_data.get('election')
        
        existing_application = Team.objects.filter(
            created_by=self.request.user,
            election=election
        ).exists()
        
        if existing_application:
            messages.error(
                self.request, 
                f"You have already submitted a team application for {election.name}. You cannot submit multiple applications for the same election."
            )
            return redirect('core:application_status')  # Redirect to status page to see existing application
        
        form.instance.created_by = self.request.user
        form.instance.status = 'PENDING'
        messages.success(self.request, "Your team application has been submitted for review.")
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['elections'] = Election.objects.filter(status__in=['PENDING', 'DRAFT'])
        
        # Add selected election to context
        election_id = self.request.GET.get('election')
        if election_id:
            try:
                context['selected_election'] = Election.objects.get(id=election_id)
            except Election.DoesNotExist:
                pass
        
        # Get user's existing team applications for reference
        context['existing_applications'] = Team.objects.filter(
            created_by=self.request.user
        ).select_related('election').order_by('-created_at')
        
        return context
@method_decorator([login_required], name='dispatch')
class ApplicationStatusView(TemplateView):
    """View for users to check their application status"""
    template_name = 'voter/application_status.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        context['candidate_applications'] = CandidateApplication.objects.filter(
            voter=user
        ).select_related('election', 'position', 'team').order_by('-applied_at')
        
        context['team_applications'] = Team.objects.filter(
            created_by=user
        ).select_related('election').order_by('-created_at')
        
        return context

# ==================== ELECTION VIEWS ====================

@method_decorator([login_required], name='dispatch')
class ElectionsView(ListView):
    """View for listing elections"""
    model = Election
    template_name = 'voter/elections.html'
    context_object_name = 'elections'
    paginate_by = 10
    
    def get_queryset(self):
        return Election.objects.all().order_by('-voting_date', '-created_at')

@method_decorator([login_required], name='dispatch')
class ElectionPositionsView(DetailView):
    """View for showing positions in an election"""
    model = Election
    template_name = 'voter/election_positions.html'
    context_object_name = 'election'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        election = self.get_object()
        context['positions'] = Position.objects.filter(election=election, is_active=True).order_by('order')
        return context

@method_decorator([login_required], name='dispatch')
class ElectionResultsView(DetailView):
    """View for election results"""
    model = Election
    template_name = 'voter/election_results.html'
    context_object_name = 'election'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        election = self.get_object()
        
        # Get results by position
        positions = Position.objects.filter(election=election, is_active=True).order_by('order')
        results_data = []
        
        for position in positions:
            candidates = Candidate.objects.filter(
                election=election,
                position=position,
                is_active=True
            ).select_related('team').order_by('-vote_count')
            
            total_votes = candidates.aggregate(total=Sum('vote_count'))['total'] or 0
            
            candidates_data = []
            for candidate in candidates:
                percentage = 0
                if total_votes > 0:
                    percentage = round((candidate.vote_count / total_votes * 100), 2)
                
                candidates_data.append({
                    'candidate': candidate,
                    'votes': candidate.vote_count,
                    'percentage': percentage,
                })
            
            results_data.append({
                'position': position,
                'candidates': candidates_data,
                'total_votes': total_votes,
            })
        
        context['results'] = results_data
        return context

# ==================== STATIC PAGE VIEWS ====================

class AboutView(TemplateView):
    """About page view"""
    template_name = 'core/about.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'About Us'
        context['page_description'] = 'Learn about our mission and values'
        return context

class MissionView(TemplateView):
    """Mission page view"""
    template_name = 'core/mission.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Our Mission'
        context['page_description'] = 'Empowering democratic processes through secure technology'
        return context

class HowItWorksView(TemplateView):
    """How It Works page view"""
    template_name = 'core/how_it_works.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'How It Works'
        context['page_description'] = 'Simple, secure, and transparent voting process'
        return context

class SecurityView(TemplateView):
    """Security page view"""
    template_name = 'core/security.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Security'
        context['page_description'] = 'Enterprise-grade security for your vote'
        return context

class FAQView(TemplateView):
    """FAQ page view"""
    template_name = 'core/faq.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Frequently Asked Questions'
        context['page_description'] = 'Find answers to common questions'
        return context

class PrivacyPolicyView(TemplateView):
    """Privacy Policy page view"""
    template_name = 'core/privacy_policy.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Privacy Policy'
        context['page_description'] = 'How we protect your data'
        return context

class TermsOfServiceView(TemplateView):
    """Terms of Service page view"""
    template_name = 'core/terms_of_service.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Terms of Service'
        context['page_description'] = 'Terms and conditions for using Agora'
        return context

class CookiePolicyView(TemplateView):
    """Cookie Policy page view"""
    template_name = 'core/cookie_policy.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Cookie Policy'
        context['page_description'] = 'How we use cookies'
        return context

class DataProtectionView(TemplateView):
    """Data Protection page view"""
    template_name = 'core/data_protection.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['page_title'] = 'Data Protection'
        context['page_description'] = 'Your data rights and protections'
        return context
# ==================== CUSTOM ERROR HANDLERS ====================

def custom_400(request, exception=None):
    """Custom 400 Bad Request error handler"""
    return render(request, 'errors/400.html', status=400)

def custom_403(request, exception=None):
    """Custom 403 Forbidden error handler"""
    return render(request, 'errors/403.html', status=403)

def custom_404(request, exception=None):
    """Custom 404 Not Found error handler"""
    return render(request, 'errors/404.html', status=404)

def custom_500(request):
    """Custom 500 Internal Server Error handler"""
    return render(request, 'errors/500.html', status=500)