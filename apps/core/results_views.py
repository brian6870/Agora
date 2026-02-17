from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.db.models import Sum
from django.utils import timezone
from django.views.decorators.cache import never_cache
import logging

from apps.accounts.models import User
from apps.voting.models import Election, Position, Candidate, Vote

logger = logging.getLogger(__name__)

@method_decorator([login_required, never_cache], name='dispatch')
class LiveResultsView(TemplateView):
    """
    View for live results - uses results.html template
    """
    template_name = 'voter/results.html'  # <-- FIXED: Using results.html for live results
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get the active or most recent election
        election = Election.objects.filter(
            status__in=['ACTIVE', 'COMPLETED']
        ).order_by('-voting_date').first()
        
        if not election:
            context['no_election'] = True
            return context
        
        context['election'] = election
        
        # Calculate overall statistics
        total_voters = User.objects.filter(
            user_type='VOTER', 
            kyc_status='VERIFIED'
        ).count()
        
        if election.election_type == 'COUNTY' and election.county:
            total_voters = User.objects.filter(
                user_type='VOTER',
                kyc_status='VERIFIED',
                county=election.county
            ).count()
        
        votes_cast = Vote.objects.filter(election=election).count()
        
        context['total_votes'] = votes_cast
        context['turnout'] = round((votes_cast / total_voters * 100), 2) if total_voters > 0 else 0
        context['eligible_voters'] = total_voters
        
        # Get all active positions
        positions = Position.objects.filter(
            election=election,
            is_active=True
        ).order_by('order')
        
        # Build results data
        results_data = []
        
        for position in positions:
            candidates = Candidate.objects.filter(
                election=election,
                position=position,
                is_active=True
            ).select_related('team').order_by('-vote_count', 'full_name')
            
            total_position_votes = candidates.aggregate(
                total=Sum('vote_count')
            )['total'] or 0
            
            for candidate in candidates:
                if total_position_votes > 0:
                    candidate.percentage = round((candidate.vote_count / total_position_votes * 100), 1)
                else:
                    candidate.percentage = 0
            
            results_data.append({
                'position': position,
                'candidates': candidates,
                'total_votes': total_position_votes,
            })
        
        context['results'] = results_data
        
        return context


@method_decorator([login_required, never_cache], name='dispatch')
class ElectionResultsView(TemplateView):
    """
    View for specific election results - uses election_results.html template
    """
    template_name = 'voter/election_results.html'  # <-- CORRECT: Using election_results.html for specific election
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get election ID from URL
        election_id = self.kwargs.get('pk')
        
        # Get the specific election
        election = get_object_or_404(Election, id=election_id)
        context['election'] = election
        
        # Calculate overall statistics
        total_voters = User.objects.filter(
            user_type='VOTER', 
            kyc_status='VERIFIED'
        ).count()
        
        if election.election_type == 'COUNTY' and election.county:
            total_voters = User.objects.filter(
                user_type='VOTER',
                kyc_status='VERIFIED',
                county=election.county
            ).count()
        
        votes_cast = Vote.objects.filter(election=election).count()
        
        context['total_votes'] = votes_cast
        context['turnout'] = round((votes_cast / total_voters * 100), 2) if total_voters > 0 else 0
        context['eligible_voters'] = total_voters
        
        # Get all active positions for this election
        positions = Position.objects.filter(
            election=election,
            is_active=True
        ).order_by('order')
        
        # Build results data
        results_data = []
        
        for position in positions:
            candidates = Candidate.objects.filter(
                election=election,
                position=position,
                is_active=True
            ).select_related('team').order_by('-vote_count', 'full_name')
            
            total_position_votes = candidates.aggregate(
                total=Sum('vote_count')
            )['total'] or 0
            
            for candidate in candidates:
                if total_position_votes > 0:
                    candidate.percentage = round((candidate.vote_count / total_position_votes * 100), 1)
                else:
                    candidate.percentage = 0
            
            results_data.append({
                'position': position,
                'candidates': candidates,
                'total_votes': total_position_votes,
            })
        
        context['results'] = results_data
        
        return context