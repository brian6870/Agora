from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models
from django.core.validators import RegexValidator, FileExtensionValidator
from django.utils import timezone
import uuid

class UserManager(BaseUserManager):
    """Custom user manager with TSC number as username"""
    
    def create_user(self, tsc_number, email, password=None, **extra_fields):
        if not tsc_number:
            raise ValueError('TSC Number is required')
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(tsc_number=tsc_number, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, tsc_number, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('user_type', 'SUPER_ADMIN')
        extra_fields.setdefault('kyc_status', 'VERIFIED')
        extra_fields.setdefault('email_verified', True)
        extra_fields.setdefault('account_status', 'ACTIVE')
        return self.create_user(tsc_number, email, password, **extra_fields)

class User(AbstractUser):
    """Custom User Model with role-based access control"""
    
    USER_TYPES = [
        ('VOTER', 'Voter'),
        ('ADMIN', 'Administrator'),
        ('SUPER_ADMIN', 'Super Administrator'),
    ]
    
    ACCOUNT_STATUS = [
        ('ACTIVE', 'Active'),
        ('SUSPENDED', 'Suspended'),
        ('PENDING', 'Pending Approval'),
        ('REJECTED', 'Rejected'),
        ('DELETED', 'Deleted'),
    ]
    
    KYC_STATUS = [
        ('PENDING', 'Pending Verification'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
        ('FLAGGED', 'Flagged for Review'),
        ('INCOMPLETE', 'Incomplete Submission'),
    ]
    
    DOCUMENT_STATUS = [
        ('NOT_UPLOADED', 'Not Uploaded'),
        ('UPLOADED', 'Uploaded'),
        ('VERIFIED', 'Verified'),
        ('REJECTED', 'Rejected'),
    ]
    
    # Remove username field - we'll use tsc_number as the identifier
    username = None
    tsc_number = models.CharField(
        max_length=20, 
        unique=True,
        validators=[RegexValidator(r'^\d+$', 'Enter a valid TSC number')],
        db_index=True,
        error_messages={
            'unique': 'A user with this TSC number already exists.',
        }
    )
    email = models.EmailField(
        unique=True, 
        db_index=True,
        error_messages={
            'unique': 'A user with this email address already exists.',
        }
    )
    email_verified = models.BooleanField(default=False)
    
    id_number = models.CharField(
        max_length=20, 
        unique=True,
        validators=[RegexValidator(r'^\d+$', 'Enter a valid ID number')],
        db_index=True,
        error_messages={
            'unique': 'A user with this ID number already exists.',
        }
    )
    full_name = models.CharField(max_length=100)
    school = models.CharField(max_length=200, blank=True, null=True)  # Made optional for admins
    county = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=15, blank=True)
    
    # User type and status
    user_type = models.CharField(max_length=20, choices=USER_TYPES, default='VOTER')
    account_status = models.CharField(max_length=20, choices=ACCOUNT_STATUS, default='PENDING')
    kyc_status = models.CharField(max_length=20, choices=KYC_STATUS, default='INCOMPLETE')
    is_active = models.BooleanField(default=True)
    
    # Admin specific fields
    admin_id = models.CharField(max_length=50, unique=True, null=True, blank=True)
    assigned_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_admins')
    assigned_at = models.DateTimeField(null=True, blank=True)
    
    # Device binding
    device_fingerprint = models.CharField(max_length=255, unique=True, null=True, blank=True, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    
    # KYC Documents
    id_front = models.ImageField(
        upload_to='kyc/ids/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        max_length=500,
        null=True,
        blank=True
    )
    id_front_status = models.CharField(max_length=20, choices=DOCUMENT_STATUS, default='NOT_UPLOADED')
    
    id_back = models.ImageField(
        upload_to='kyc/ids/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        max_length=500,
        blank=True,
        null=True
    )
    id_back_status = models.CharField(max_length=20, choices=DOCUMENT_STATUS, default='NOT_UPLOADED')
    
    face_photo = models.ImageField(
        upload_to='kyc/faces/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        max_length=500,
        null=True,
        blank=True
    )
    face_photo_status = models.CharField(max_length=20, choices=DOCUMENT_STATUS, default='NOT_UPLOADED')
    
    # Liveness check data
    liveness_confidence = models.FloatField(null=True, blank=True)
    liveness_check_passed = models.BooleanField(default=False)
    
    # TSC verification
    tsc_verified = models.BooleanField(default=False)
    tsc_verified_at = models.DateTimeField(null=True, blank=True)
    tsc_verified_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='tsc_verified_users')
    
    # Voting status
    has_voted = models.BooleanField(default=False)
    voted_at = models.DateTimeField(null=True, blank=True)
    vote_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    
    # Account deletion request
    deletion_requested = models.BooleanField(default=False)
    deletion_requested_at = models.DateTimeField(null=True, blank=True)
    deletion_approved_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='deleted_users')
    deleted_at = models.DateTimeField(null=True, blank=True)
    deletion_reason = models.TextField(blank=True)
    
    # Account suspension
    suspended_at = models.DateTimeField(null=True, blank=True)
    suspended_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='suspended_users')
    suspension_reason = models.TextField(blank=True)
    suspension_lifted_at = models.DateTimeField(null=True, blank=True)
    suspension_lifted_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='suspension_lifted_users')
    
    # Password reset
    reset_password_token = models.UUIDField(null=True, blank=True)
    reset_password_sent_at = models.DateTimeField(null=True, blank=True)
    
    # Timestamps
    registered_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        'self', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_voters'
    )
    kyc_submitted_at = models.DateTimeField(null=True, blank=True)
    kyc_verified_at = models.DateTimeField(null=True, blank=True)
    kyc_verified_by = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='kyc_verified_users')
    
    USERNAME_FIELD = 'tsc_number'
    REQUIRED_FIELDS = ['email', 'id_number', 'full_name', 'county']
    
    objects = UserManager()
    
    class Meta:
        indexes = [
            models.Index(fields=['tsc_number', 'kyc_status']),
            models.Index(fields=['device_fingerprint']),
            models.Index(fields=['email']),
            models.Index(fields=['county', 'school']),
            models.Index(fields=['user_type', 'account_status']),
            models.Index(fields=['tsc_verified']),
            models.Index(fields=['deletion_requested']),
        ]
    
    def __str__(self):
        return f"{self.full_name} - {self.tsc_number} ({self.user_type})"
    
    def save(self, *args, **kwargs):
        # Django's AbstractUser expects a username field
        # Set it to tsc_number to avoid conflicts
        self.username = self.tsc_number
        super().save(*args, **kwargs)
    
    # Role check methods
    def is_super_admin(self):
        return self.user_type == 'SUPER_ADMIN'
    
    def is_admin(self):
        return self.user_type in ['ADMIN', 'SUPER_ADMIN']
    
    def is_voter(self):
        return self.user_type == 'VOTER'
    
    # Permission check methods
    def can_manage_elections(self):
        """Only super admins can manage election dates and timers"""
        return self.user_type == 'SUPER_ADMIN'
    
    def can_manage_admins(self):
        """Only super admins can create and approve admin accounts"""
        return self.user_type == 'SUPER_ADMIN'
    
    def can_manage_candidates(self):
        """Both admins and super admins can manage candidates"""
        return self.user_type in ['ADMIN', 'SUPER_ADMIN']
    
    def can_verify_kyc(self):
        """Both admins and super admins can verify KYC"""
        return self.user_type in ['ADMIN', 'SUPER_ADMIN']
    
    def can_verify_tsc(self):
        """Both admins and super admins can verify TSC numbers"""
        return self.user_type in ['ADMIN', 'SUPER_ADMIN']
    
    def can_suspend_accounts(self):
        """Both admins and super admins can suspend accounts"""
        return self.user_type in ['ADMIN', 'SUPER_ADMIN']
    
    def can_delete_accounts(self):
        """Both admins and super admins can delete accounts"""
        return self.user_type in ['ADMIN', 'SUPER_ADMIN']
    
    def can_view_reports(self):
        """Both admins and super admins can view reports"""
        return self.user_type in ['ADMIN', 'SUPER_ADMIN']
    
    def can_access_admin_panel(self):
        """Both admins and super admins can access admin panel"""
        return self.user_type in ['ADMIN', 'SUPER_ADMIN']


class AdminProfile(models.Model):
    """Profile for administrators with verification details"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='admin_profile')
    national_id = models.CharField(max_length=20, unique=True)
    county_of_residence = models.CharField(max_length=100)
    id_document = models.ImageField(
        upload_to='admin/ids/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])]
    )
    id_back_document = models.ImageField(
        upload_to='admin/ids/back/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])],
        null=True,
        blank=True
    )
    selfie_photo = models.ImageField(
        upload_to='admin/faces/',
        validators=[FileExtensionValidator(['jpg', 'jpeg', 'png'])]
    )
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='verified_admins'
    )
    rejection_reason = models.TextField(blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['national_id', 'is_verified']),
        ]
    
    def __str__(self):
        return f"Admin Profile: {self.user.full_name} ({'Verified' if self.is_verified else 'Pending'})"


class EmailVerificationOTP(models.Model):
    """Model for email verification OTPs"""
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='email_verification', null=True, blank=True)
    email = models.EmailField(db_index=True)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    
    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timezone.timedelta(minutes=10)
        super().save(*args, **kwargs)
    
    class Meta:
        indexes = [
            models.Index(fields=['otp', 'is_used']),
            models.Index(fields=['email', 'is_used']),
        ]
    
    def __str__(self):
        return f"OTP for {self.email}"


class AccountActionRequest(models.Model):
    """Model for tracking account actions like deletion, suspension, etc."""
    
    ACTION_TYPES = [
        ('DELETE', 'Delete Account'),
        ('SUSPEND', 'Suspend Account'),
        ('REACTIVATE', 'Reactivate Account'),
        ('KYC_VERIFY', 'KYC Verification'),
        ('TSC_VERIFY', 'TSC Verification'),
        ('DEVICE_RESET', 'Device Reset'),
        ('ADMIN_APPROVAL', 'Admin Approval'),
        ('PASSWORD_RESET', 'Password Reset'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
        ('COMPLETED', 'Completed'),
        ('CANCELLED', 'Cancelled'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='action_requests')
    action_type = models.CharField(max_length=20, choices=ACTION_TYPES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='requested_actions')
    requested_at = models.DateTimeField(auto_now_add=True)
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_actions')
    processed_at = models.DateTimeField(null=True, blank=True)
    reason = models.TextField(blank=True)
    admin_notes = models.TextField(blank=True, help_text="Internal notes for administrators")
    metadata = models.JSONField(default=dict, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'action_type', 'status']),
            models.Index(fields=['requested_at']),
            models.Index(fields=['status', 'action_type']),
        ]
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.get_action_type_display()} ({self.get_status_display()})"


class Notification(models.Model):
    """Notification model for user alerts and messages"""
    
    NOTIFICATION_TYPES = [
        ('INFO', 'Information'),
        ('SUCCESS', 'Success'),
        ('WARNING', 'Warning'),
        ('ERROR', 'Error'),
        ('ACTION_REQUIRED', 'Action Required'),
    ]
    
    PRIORITY_LEVELS = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='INFO')
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='MEDIUM')
    is_read = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    is_email_sent = models.BooleanField(default=False)
    action_url = models.CharField(max_length=500, blank=True)
    action_text = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    read_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_read']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['notification_type', 'priority']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.full_name} - {self.title}"
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = timezone.now()
        self.save()
    
    @classmethod
    def create_for_user(cls, user, title, message, notification_type='INFO', priority='MEDIUM', action_url='', action_text='', metadata=None):
        """Helper method to create a notification for a user"""
        return cls.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            action_url=action_url,
            action_text=action_text,
            metadata=metadata or {}
        )


class AuditLog(models.Model):
    """Audit log for tracking important actions in the system"""
    
    ACTION_CATEGORIES = [
        ('USER', 'User Management'),
        ('ADMIN', 'Admin Management'),
        ('ELECTION', 'Election Management'),
        ('VOTING', 'Voting'),
        ('KYC', 'KYC Verification'),
        ('SECURITY', 'Security'),
        ('SYSTEM', 'System'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=255)
    category = models.CharField(max_length=50, choices=ACTION_CATEGORIES, default='SYSTEM')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    details = models.JSONField(default=dict, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['category', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.timestamp} - {self.action} - {self.user}"
    
    @classmethod
    def log(cls, user, action, category='SYSTEM', request=None, details=None):
        """Helper method to create an audit log entry"""
        ip = None
        user_agent = None
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip = x_forwarded_for.split(',')[0]
            else:
                ip = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        return cls.objects.create(
            user=user,
            action=action,
            category=category,
            ip_address=ip,
            user_agent=user_agent,
            details=details or {}
        )