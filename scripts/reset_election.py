
#!/usr/bin/env python
"""Script to reset election data for testing or new election cycle"""
import os
import sys
import django
from django.db import transaction
from django.utils import timezone

sys.path.append('/var/www/agora')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'agora_backend.settings')
django.setup()

from apps.accounts.models import User
from apps.voting.models import Vote, Candidate, ElectionSettings
from apps.core.models import DeviceResetRequest

def reset_election(confirm=False):
    """
    Reset election data while preserving user registrations
    """
    if not confirm:
        print("⚠️  This will delete ALL votes and reset candidate counts!")
        print("User accounts and KYC data will be preserved.")
        response = input("Type 'RESET' to confirm: ")
        if response != 'RESET':
            print("Reset cancelled.")
            return
    
    with transaction.atomic():
        # Delete all votes
        vote_count = Vote.objects.count()
        Vote.objects.all().delete()
        print(f"✓ Deleted {vote_count} votes")
        
        # Reset candidate vote counts
        candidates = Candidate.objects.all()
        for candidate in candidates:
            candidate.vote_count = 0
            candidate.save()
        print(f"✓ Reset vote counts for {candidates.count()} candidates")
        
        # Reset user voting status
        voters = User.objects.filter(has_voted=True)
        for voter in voters:
            voter.has_voted = False
            voter.voted_at = None
            voter.save()
        print(f"✓ Reset voting status for {voters.count()} users")
        
        # Reset election settings
        settings = ElectionSettings.get_settings()
        settings.total_votes_cast = 0
        settings.status = 'PENDING'
        settings.allow_voting = False
        settings.emergency_pause = False
        settings.save()
        print("✓ Reset election settings")
        
        # Delete old device reset requests
        old_requests = DeviceResetRequest.objects.filter(
            status__in=['APPROVED', 'REJECTED', 'EXPIRED']
        )
        old_count = old_requests.count()
        old_requests.delete()
        print(f"✓ Cleaned up {old_count} old device reset requests")
        
        print("\n✅ Election reset complete!")
        print(f"Current time: {timezone.now()}")
        print("System is ready for new election.")

if __name__ == '__main__':
    reset_election(confirm='--force' in sys.argv)