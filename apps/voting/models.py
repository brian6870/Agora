from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.utils import timezone
from apps.accounts.models import User
import uuid

class Election(models.Model):
    """Main Election model - supports multiple elections"""
    ELECTION_TYPES = [
        ('NATIONAL', 'National Wide'),
        ('COUNTY', 'County Based'),
    ]
    
    ELECTION_STATUS = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending'),
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('ARCHIVED', 'Archived'),
    ]
    
    name = models.CharField(max_length=200)
    election_type = models.CharField(max_length=20, choices=ELECTION_TYPES, default='NATIONAL')
    county = models.CharField(max_length=100, blank=True, null=True, help_text="Required only for county-based elections")
    description = models.TextField(blank=True)
    
    # Voting window
    voting_date = models.DateField(null=True, blank=True)
    voting_start_time = models.TimeField(default="08:00:00")
    voting_end_time = models.TimeField(default="17:00:00")
    
    # Status
    status = models.CharField(max_length=20, choices=ELECTION_STATUS, default='DRAFT')
    allow_voting = models.BooleanField(default=False)
    results_published = models.BooleanField(default=False)
    
    # Emergency controls
    emergency_pause = models.BooleanField(default=False)
    pause_reason = models.TextField(blank=True)
    
    # Statistics (denormalized)
    total_voters_eligible = models.IntegerField(default=0)
    total_votes_cast = models.IntegerField(default=0)
    
    # Auto controls
    auto_open = models.BooleanField(default=True)
    auto_close = models.BooleanField(default=True)
    auto_publish = models.BooleanField(default=False)
    
    # Reminders
    reminder_24h = models.BooleanField(default=True)
    reminder_1h = models.BooleanField(default=True)
    reminder_start = models.BooleanField(default=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_elections')
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['status', 'voting_date']),
            models.Index(fields=['election_type', 'county']),
        ]
        ordering = ['-voting_date', '-created_at']
    
    def __str__(self):
        return f"{self.name} ({self.get_election_type_display()})"
    
    def is_voting_open(self):
        """Check if voting is currently open for this election"""
        # First check basic flags
        if not self.allow_voting or self.emergency_pause or self.status != 'ACTIVE':
            return False
        
        # If no voting date is set, consider it open based on status only
        if not self.voting_date:
            return self.allow_voting and not self.emergency_pause and self.status == 'ACTIVE'
        
        now = timezone.now()
        # Convert to local timezone for date comparison
        local_now = timezone.localtime(now)
        current_date = local_now.date()
        current_time = local_now.time()
        
        # Check if it's the voting date (using local date)
        if current_date != self.voting_date:
            return False
        
        # Handle midnight crossover cases
        start_time = self.voting_start_time
        end_time = self.voting_end_time
        
        # If end time is less than start time, it means voting crosses midnight
        if end_time <= start_time:
            # For times crossing midnight, we need special handling
            if current_time >= start_time or current_time < end_time:
                return True
        else:
            # Normal case: start_time <= current_time <= end_time
            if start_time <= current_time <= end_time:
                return True
        
        return False
    
    def get_voting_status_display(self):
        """Get a human-readable voting status"""
        if not self.allow_voting:
            return "Voting Disabled"
        if self.emergency_pause:
            return f"Paused: {self.pause_reason}"
        if self.status != 'ACTIVE':
            return f"Election {self.get_status_display()}"
        if not self.voting_date:
            return "No Date Set"
        
        now = timezone.now()
        local_now = timezone.localtime(now)
        current_date = local_now.date()
        current_time = local_now.time()
        
        if current_date < self.voting_date:
            return "Upcoming"
        elif current_date > self.voting_date:
            return "Passed"
        else:
            # Today is voting day
            if current_time < self.voting_start_time:
                return "Opens Soon"
            elif self.voting_end_time <= self.voting_start_time and current_time >= self.voting_start_time:
                # Crosses midnight, open until end time tomorrow
                return "Open"
            elif self.voting_start_time <= current_time <= self.voting_end_time:
                return "Open"
            elif current_time > self.voting_end_time and self.voting_end_time > self.voting_start_time:
                return "Closed"
            else:
                return "Open" if self.is_voting_open() else "Closed"
    
    def get_eligible_voters(self):
        """Get queryset of eligible voters for this election"""
        from apps.accounts.models import User
        
        if self.election_type == 'NATIONAL':
            return User.objects.filter(user_type='VOTER', kyc_status='VERIFIED')
        else:  # COUNTY
            return User.objects.filter(
                user_type='VOTER', 
                kyc_status='VERIFIED',
                county=self.county
            )
    
    def get_eligible_count(self):
        """Get count of eligible voters"""
        return self.get_eligible_voters().count()
    
    def check_and_update_status(self):
        """Check if election status should be updated based on current time"""
        if self.status == 'PENDING' and self.auto_open:
            if self.should_be_active():
                self.status = 'ACTIVE'
                self.save()
                return True
        
        elif self.status == 'ACTIVE' and self.auto_close:
            if self.should_be_completed():
                self.status = 'COMPLETED'
                self.allow_voting = False
                self.save()
                return True
        
        elif self.status == 'COMPLETED' and self.auto_publish and not self.results_published:
            self.results_published = True
            self.save()
            return True
        
        return False

    def should_be_active(self):
        """Check if election should be active now"""
        if self.status != 'PENDING':
            return False
        
        now = timezone.now()
        local_now = timezone.localtime(now)
        
        return (local_now.date() == self.voting_date and 
                local_now.time() >= self.voting_start_time)

    def should_be_completed(self):
        """Check if election should be completed now"""
        if self.status != 'ACTIVE':
            return False
        
        now = timezone.now()
        local_now = timezone.localtime(now)
        
        return (local_now.date() > self.voting_date or
                (local_now.date() == self.voting_date and 
                 local_now.time() >= self.voting_end_time))
    
    def save(self, *args, **kwargs):
        if self.election_type == 'NATIONAL':
            self.county = None
        super().save(*args, **kwargs)


class Position(models.Model):
    """Union positions available for election - linked to specific election"""
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='positions')
    order = models.IntegerField()
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    max_votes = models.IntegerField(default=1)
    is_active = models.BooleanField(default=True)
    
    # Candidate requirements
    require_team = models.BooleanField(default=False)
    require_manifesto = models.BooleanField(default=False)
    require_bio = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['election', 'order']
        unique_together = ['election', 'order']
    
    def __str__(self):
        return f"{self.election.name} - {self.name}"


class Team(models.Model):
    """Candidate teams/alliances - linked to specific election"""
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='teams')
    name = models.CharField(max_length=100)
    acronym = models.CharField(max_length=20, blank=True)
    logo = models.ImageField(upload_to='teams/', null=True, blank=True)
    color_code = models.CharField(max_length=7, default="#000000")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    
    # Who created this team (voter who applied)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_teams')
    
    # Application status
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reviewed_teams')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['election', 'status']),
        ]
        unique_together = ['election', 'name']
    
    def __str__(self):
        return f"{self.election.name} - {self.name}"


class CandidateApplication(models.Model):
    """Candidate applications from voters"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='candidate_applications')
    voter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='candidate_applications')
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='applications')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='applications')
    
    # Application details
    manifesto = models.TextField(blank=True)
    bio = models.TextField(blank=True)
    photo = models.ImageField(upload_to='candidate_applications/', null=True, blank=True)
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='reviewed_applications')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    
    # If approved, creates a candidate record (One-to-One with unique related_name)
    approved_candidate = models.OneToOneField(
        'Candidate', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='source_application'  # Changed from 'application' to avoid clash
    )
    
    applied_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['election', 'status']),
            models.Index(fields=['voter', 'election']),
        ]
        unique_together = ['election', 'voter', 'position']  # One application per position per voter
    
    def __str__(self):
        return f"{self.voter.full_name} - {self.position.name} ({self.status})"


class Candidate(models.Model):
    """Candidates running for positions"""
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='candidates')
    position = models.ForeignKey(Position, on_delete=models.CASCADE, related_name='candidates')
    team = models.ForeignKey(Team, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidates')
    
    # Candidate info (can be from application or manually added)
    full_name = models.CharField(max_length=100)
    photo = models.ImageField(upload_to='candidates/', null=True, blank=True)
    bio = models.TextField(blank=True)
    manifesto = models.TextField(blank=True)
    
    # If created from application
    application = models.OneToOneField(
        CandidateApplication, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='created_candidate'  # Changed from 'approved_candidate' to be more consistent
    )
    voter = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='candidacies')
    
    # Metadata
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    added_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='added_candidates')
    added_at = models.DateTimeField(auto_now_add=True)
    
    # Statistics
    vote_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['election', 'position__order', 'order', 'full_name']
        indexes = [
            models.Index(fields=['election', 'position', 'vote_count']),
            models.Index(fields=['election', 'team']),
        ]
        unique_together = ['election', 'position', 'full_name']  # Prevent duplicate names in same position
    
    def __str__(self):
        return f"{self.election.name} - {self.position.name} - {self.full_name}"
    
    def increment_vote(self):
        from django.db.models import F
        self.vote_count = F('vote_count') + 1
        self.save(update_fields=['vote_count'])


class Vote(models.Model):
    """Individual vote records - linked to specific election"""
    election = models.ForeignKey(Election, on_delete=models.PROTECT, related_name='votes')
    voter = models.ForeignKey(User, on_delete=models.PROTECT, related_name='votes')
    
    # Vote data
    candidates = models.ManyToManyField(Candidate, related_name='votes')
    vote_hash = models.CharField(max_length=256, unique=True)
    
    # Metadata
    ip_address = models.GenericIPAddressField()
    device_fingerprint = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    vote_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['election', 'timestamp']),
            models.Index(fields=['voter', 'election']),
        ]
        unique_together = ['election', 'voter']  # One vote per election per voter
    
    def __str__(self):
        return f"{self.election.name} - {self.voter.full_name} - {self.timestamp}"
    
    def save(self, *args, **kwargs):
        if not self.vote_hash:
            import hashlib
            import json
            vote_data = {
                'voter': self.voter.tsc_number,
                'election': self.election.id,
                'timestamp': str(self.timestamp),
                'token': str(self.vote_token)
            }
            self.vote_hash = hashlib.sha256(
                json.dumps(vote_data, sort_keys=True).encode()
            ).hexdigest()
        super().save(*args, **kwargs)


class VoteAuditLog(models.Model):
    """Audit trail for all voting activities"""
    ACTION_TYPES = [
        ('VOTE_CAST', 'Vote Cast'),
        ('VOTE_VERIFIED', 'Vote Verified'),
        ('VOTE_INVALIDATED', 'Vote Invalidated'),
        ('BALLOT_OPENED', 'Ballot Opened'),
        ('BALLOT_CLOSED', 'Ballot Closed'),
    ]
    
    election = models.ForeignKey(Election, on_delete=models.CASCADE, related_name='audit_logs')
    vote = models.ForeignKey(Vote, on_delete=models.SET_NULL, null=True, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    ip_address = models.GenericIPAddressField()
    user_agent = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    metadata = models.JSONField(default=dict)
    
    class Meta:
        indexes = [
            models.Index(fields=['election', 'action', 'timestamp']),
        ]
        ordering = ['-timestamp']


class ElectionSettings(models.Model):
    """Legacy model for backward compatibility - will be phased out"""
    @classmethod
    def get_settings(cls):
        # Return default settings for backward compatibility
        from django.utils import timezone
        settings, created = cls.objects.get_or_create(
            pk=1,
            defaults={
                'election_name': 'Default Election',
                'status': 'PENDING'
            }
        )
        return settings
    
    # Keep existing fields but make them optional
    election_name = models.CharField(max_length=200, default="Default Election")
    voting_date = models.DateField(null=True, blank=True)
    voting_start_time = models.TimeField(default="08:00:00")
    voting_end_time = models.TimeField(default="17:00:00")
    status = models.CharField(max_length=20, default='PENDING')
    allow_voting = models.BooleanField(default=False)
    results_published = models.BooleanField(default=False)
    emergency_pause = models.BooleanField(default=False)
    pause_reason = models.TextField(blank=True)
    total_voters = models.IntegerField(default=0)
    total_votes_cast = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "Legacy Election Setting"
        verbose_name_plural = "Legacy Election Settings"