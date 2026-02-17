from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction
from apps.voting.models import Election
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Process election status transitions (auto-open, auto-close, auto-publish)'
    
    def handle(self, *args, **options):
        self.stdout.write(f"Processing elections at {timezone.now()}")
        
        now = timezone.now()
        current_date = now.date()
        current_time = now.time()
        
        # Process auto-open elections
        self.auto_open_elections(current_date, current_time)
        
        # Process auto-close elections
        self.auto_close_elections(current_date, current_time)
        
        # Process auto-publish elections
        self.auto_publish_elections()
        
        self.stdout.write(self.style.SUCCESS('Election processing completed'))
    
    def auto_open_elections(self, current_date, current_time):
        """Auto-open elections that should start now"""
        elections = Election.objects.filter(
            status='PENDING',
            auto_open=True,
            voting_date=current_date,
            voting_start_time__lte=current_time,
            allow_voting=True
        )
        
        count = 0
        for election in elections:
            with transaction.atomic():
                election.status = 'ACTIVE'
                election.save()
                count += 1
                logger.info(f"Auto-opened election: {election.name}")
                self.stdout.write(f"Opened: {election.name}")
        
        self.stdout.write(f"Auto-opened {count} elections")
    
    def auto_close_elections(self, current_date, current_time):
        """Auto-close elections that should end now"""
        elections = Election.objects.filter(
            status='ACTIVE',
            auto_close=True,
            voting_date=current_date,
            voting_end_time__lte=current_time
        )
        
        count = 0
        for election in elections:
            with transaction.atomic():
                election.status = 'COMPLETED'
                election.allow_voting = False
                election.save()
                count += 1
                logger.info(f"Auto-closed election: {election.name}")
                self.stdout.write(f"Closed: {election.name}")
        
        self.stdout.write(f"Auto-closed {count} elections")
    
    def auto_publish_elections(self):
        """Auto-publish results for completed elections"""
        elections = Election.objects.filter(
            status='COMPLETED',
            auto_publish=True,
            results_published=False
        )
        
        count = 0
        for election in elections:
            with transaction.atomic():
                election.results_published = True
                election.save()
                count += 1
                logger.info(f"Auto-published results for: {election.name}")
                self.stdout.write(f"Published results: {election.name}")
        
        self.stdout.write(f"Auto-published {count} elections")