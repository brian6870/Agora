# apps/core/models.py - Updated Version with proper voting time logic
from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils import timezone
import uuid

class TimeStampedModel(models.Model):
    """Abstract base model with timestamp fields"""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class ElectionSettings(TimeStampedModel):
    """Global election configuration"""
    ELECTION_STATUS = [
        ('PENDING', 'Pending'),
        ('SETUP', 'Setup'),
        ('ACTIVE', 'Active'),
        ('PAUSED', 'Paused'),
        ('COMPLETED', 'Completed'),
        ('ARCHIVED', 'Archived'),
    ]
    
    election_name = models.CharField(max_length=200, default="Teacher Union Elections 2024")
    voting_date = models.DateField(null=True, blank=True)
    voting_start_time = models.TimeField(default="08:00:00")
    voting_end_time = models.TimeField(default="17:00:00")
    status = models.CharField(max_length=20, choices=ELECTION_STATUS, default='PENDING')
    allow_voting = models.BooleanField(default=False)
    results_published = models.BooleanField(default=False)
    
    # Emergency controls
    emergency_pause = models.BooleanField(default=False)
    pause_reason = models.TextField(blank=True)
    
    # Statistics
    total_voters = models.IntegerField(default=0)
    total_votes_cast = models.IntegerField(default=0)
    
    class Meta:
        verbose_name = "Election Setting"
        verbose_name_plural = "Election Settings"
    
    def save(self, *args, **kwargs):
        if not self.pk and ElectionSettings.objects.exists():
            # Instead of raising error, update the existing one
            existing = ElectionSettings.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create default settings"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
    
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
    
    def __str__(self):
        return f"{self.election_name} - {self.status}"

class DeviceResetRequest(TimeStampedModel):
    """Device change requests from voters"""
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
    ]
    
    tsc_number = models.CharField(max_length=20, db_index=True)
    id_number = models.CharField(max_length=20)
    full_name = models.CharField(max_length=100)
    reason = models.TextField()
    new_device_fingerprint = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    reviewed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_requests'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    request_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['tsc_number', 'status']),
            models.Index(fields=['created_at']),
        ]
    
    def can_approve(self):
        """Check if request is within 3-day rule"""
        try:
            election = ElectionSettings.get_settings()
            if election.voting_date:
                days_before = (election.voting_date - self.request_date.date()).days
                return days_before >= 3
        except:
            pass
        return True
    
    def __str__(self):
        return f"Reset Request - {self.tsc_number} ({self.status})"
class MaintenanceMode(models.Model):
    """Maintenance mode configuration"""
    is_active = models.BooleanField(default=False)
    message = models.TextField(default="System is currently under maintenance. Please check back later.")
    allowed_ips = models.TextField(blank=True, help_text="IP addresses allowed during maintenance (one per line)")
    
    # Scheduled maintenance
    scheduled_start = models.DateTimeField(null=True, blank=True)
    scheduled_end = models.DateTimeField(null=True, blank=True)
    estimated_end = models.DateTimeField(null=True, blank=True)
    
    # Notifications
    notify_users = models.BooleanField(default=False)
    notification_sent = models.BooleanField(default=False)
    
    # Stats
    enabled_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True)
    enabled_at = models.DateTimeField(auto_now_add=True)
    disabled_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = "Maintenance Mode"
        verbose_name_plural = "Maintenance Mode"
    
    def __str__(self):
        return f"Maintenance Mode: {'Active' if self.is_active else 'Inactive'}"
    
    def save(self, *args, **kwargs):
        if not self.pk and MaintenanceMode.objects.exists():
            # Update existing record instead of creating new one
            existing = MaintenanceMode.objects.first()
            self.pk = existing.pk
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
class SystemLog(models.Model):
    """System log entries"""
    LEVEL_CHOICES = [
        ('DEBUG', 'Debug'),
        ('INFO', 'Info'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('CRITICAL', 'Critical'),
    ]
    
    level = models.CharField(max_length=10, choices=LEVEL_CHOICES, default='INFO')
    message = models.TextField()
    traceback = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"[{self.timestamp}] {self.level}: {self.message[:50]}"
class PerformanceMetric(models.Model):
    """System performance metrics"""
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    response_time = models.FloatField(help_text="Average response time in ms")
    request_rate = models.FloatField(help_text="Requests per second")
    error_rate = models.FloatField(help_text="Error percentage")
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"Performance at {self.timestamp}"