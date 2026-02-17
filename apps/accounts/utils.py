from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from .models import Notification, AuditLog
import logging

logger = logging.getLogger(__name__)

# ==================== NOTIFICATION FUNCTIONS ====================

def create_notification(user, title, message, notification_type='INFO', priority='MEDIUM', action_url='', action_text='', metadata=None):
    """
    Create an in-app notification for a user
    
    Args:
        user: User object to notify
        title: Notification title
        message: Notification message
        notification_type: Type of notification (INFO, SUCCESS, WARNING, ERROR, ACTION_REQUIRED)
        priority: Priority level (LOW, MEDIUM, HIGH, URGENT)
        action_url: URL for action button
        action_text: Text for action button
        metadata: Additional metadata as dict
    
    Returns:
        Notification object
    """
    try:
        notification = Notification.objects.create(
            user=user,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            action_url=action_url,
            action_text=action_text,
            metadata=metadata or {}
        )
        logger.info(f"Notification created for user {user.id}: {title}")
        return notification
    except Exception as e:
        logger.error(f"Failed to create notification for user {user.id}: {e}")
        return None


def create_bulk_notifications(users, title, message, notification_type='INFO', priority='MEDIUM'):
    """
    Create notifications for multiple users efficiently
    
    Args:
        users: QuerySet or list of User objects
        title: Notification title
        message: Notification message
        notification_type: Type of notification
        priority: Priority level
    
    Returns:
        Number of notifications created
    """
    notifications = []
    for user in users:
        notifications.append(
            Notification(
                user=user,
                title=title,
                message=message,
                notification_type=notification_type,
                priority=priority
            )
        )
    
    if notifications:
        try:
            created = Notification.objects.bulk_create(notifications)
            logger.info(f"Created {len(created)} bulk notifications")
            return len(created)
        except Exception as e:
            logger.error(f"Failed to create bulk notifications: {e}")
            return 0
    return 0


# ==================== EMAIL NOTIFICATION FUNCTIONS ====================

def send_notification_email(user, subject, template_name, context=None):
    """Send notification email to user"""
    if not user or not user.email:
        logger.warning(f"No email for user {user.id if user else 'unknown'}")
        return False
    
    if context is None:
        context = {}
    
    context.update({
        'user': user,
        'site_name': 'Agora Voting Platform',
        'support_email': settings.DEFAULT_FROM_EMAIL,
        'current_year': timezone.now().year,
    })
    
    try:
        html_message = render_to_string(f'emails/{template_name}.html', context)
        plain_message = strip_tags(html_message)
        
        send_mail(
            subject,
            plain_message,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Email sent to {user.email}: {subject}")
        
        # Also create in-app notification
        create_notification(
            user=user,
            title=subject,
            message=plain_message[:200] + ('...' if len(plain_message) > 200 else ''),
            notification_type='INFO'
        )
        
        return True
    except Exception as e:
        logger.error(f"Failed to send email to {user.email}: {e}")
        return False


def send_account_request_received(user, request_type):
    """Send notification that request has been received"""
    subject = f"{request_type} Request Received - Agora"
    
    # Create in-app notification
    create_notification(
        user=user,
        title=subject,
        message=f"Your {request_type} request has been received and is being processed.",
        notification_type='INFO'
    )
    
    return send_notification_email(
        user,
        subject,
        'request_received',
        {'request_type': request_type}
    )


def send_account_request_approved(user, request_type, login_url=None):
    """Send notification that request has been approved"""
    subject = f"{request_type} Request Approved - Agora"
    
    # Create in-app notification
    create_notification(
        user=user,
        title=subject,
        message=f"Your {request_type} request has been approved.",
        notification_type='SUCCESS',
        action_url=login_url,
        action_text='Log In' if login_url else None
    )
    
    return send_notification_email(
        user,
        subject,
        'request_approved',
        {
            'request_type': request_type,
            'login_url': login_url,
        }
    )


def send_account_request_rejected(user, request_type, reason):
    """Send notification that request has been rejected"""
    subject = f"{request_type} Request Update - Agora"
    
    # Create in-app notification
    create_notification(
        user=user,
        title=subject,
        message=f"Your {request_type} request could not be approved. Reason: {reason}",
        notification_type='WARNING'
    )
    
    return send_notification_email(
        user,
        subject,
        'request_rejected',
        {
            'request_type': request_type,
            'reason': reason,
        }
    )


def send_admin_approval_request(superuser, admin_user):
    """Send notification to superuser about new admin approval request"""
    subject = f"New Admin Approval Request - {admin_user.full_name}"
    
    # Create in-app notification for superuser
    create_notification(
        user=superuser,
        title=subject,
        message=f"{admin_user.full_name} has requested admin access. Please review their application.",
        notification_type='ACTION_REQUIRED',
        priority='HIGH',
        action_url='/admin-panel/pending-admins/',
        action_text='Review Request'
    )
    
    return send_notification_email(
        superuser,
        subject,
        'admin_approval_request',
        {'admin_user': admin_user}
    )


def send_account_deletion_confirmation(user):
    """Send confirmation of account deletion"""
    subject = "Account Deletion Confirmation - Agora"
    
    # Create in-app notification (though user might be deleted soon)
    create_notification(
        user=user,
        title=subject,
        message="Your account has been deleted as requested.",
        notification_type='INFO'
    )
    
    return send_notification_email(
        user,
        subject,
        'account_deleted',
        {}
    )


def send_account_suspension_notice(user, reason):
    """Send notice of account suspension"""
    subject = "Account Suspension Notice - Agora"
    
    # Create in-app notification
    create_notification(
        user=user,
        title=subject,
        message=f"Your account has been suspended. Reason: {reason}",
        notification_type='WARNING',
        priority='HIGH'
    )
    
    return send_notification_email(
        user,
        subject,
        'account_suspended',
        {'reason': reason}
    )


def send_account_reactivation_notice(user):
    """Send notice of account reactivation"""
    subject = "Account Reactivated - Agora"
    
    # Create in-app notification
    create_notification(
        user=user,
        title=subject,
        message="Your account has been reactivated. You can now log in.",
        notification_type='SUCCESS',
        action_url='/accounts/login/',
        action_text='Log In'
    )
    
    return send_notification_email(
        user,
        subject,
        'account_reactivated',
        {}
    )


def send_kyc_verification_notice(user, status):
    """Send notice of KYC verification status"""
    subject = f"KYC Verification {status} - Agora"
    
    # Create in-app notification
    notification_type = 'SUCCESS' if status == 'Verified' else 'WARNING'
    create_notification(
        user=user,
        title=subject,
        message=f"Your KYC verification has been {status.lower()}.",
        notification_type=notification_type
    )
    
    return send_notification_email(
        user,
        subject,
        'kyc_verification',
        {'status': status}
    )


def send_tsc_verification_notice(user, status):
    """Send notice of TSC verification status"""
    subject = f"TSC Verification {status} - Agora"
    
    # Create in-app notification
    notification_type = 'SUCCESS' if status == 'Verified' else 'WARNING'
    create_notification(
        user=user,
        title=subject,
        message=f"Your TSC number verification has been {status.lower()}.",
        notification_type=notification_type
    )
    
    return send_notification_email(
        user,
        subject,
        'tsc_verification',
        {'status': status}
    )


def send_welcome_email(user):
    """Send welcome email to new user"""
    subject = "Welcome to Agora - Complete Your Registration"
    
    # Create in-app notification
    create_notification(
        user=user,
        title="Welcome to Agora!",
        message="Thank you for registering. Please complete your KYC verification to start voting.",
        notification_type='SUCCESS',
        action_url='/accounts/kyc/',
        action_text='Complete KYC'
    )
    
    return send_notification_email(
        user,
        subject,
        'welcome_email',
        {}
    )


def send_election_reminder(user, election):
    """Send election reminder to voter"""
    subject = f"Election Reminder: {election.election_name}"
    
    # Create in-app notification
    create_notification(
        user=user,
        title="Election Reminder",
        message=f"Voting for {election.election_name} opens soon. Don't forget to cast your vote!",
        notification_type='INFO',
        priority='HIGH',
        action_url='/vote/',
        action_text='Vote Now'
    )
    
    return send_notification_email(
        user,
        subject,
        'election_reminder',
        {'election': election}
    )


# ==================== AUDIT LOG FUNCTIONS ====================

def log_audit_action(user, action, category='SYSTEM', request=None, details=None):
    """Helper function to log audit actions"""
    ip_address = None
    user_agent = None
    
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
        user_agent = request.META.get('HTTP_USER_AGENT', '')
    
    try:
        audit_log = AuditLog.objects.create(
            user=user,
            action=action,
            category=category,
            ip_address=ip_address,
            user_agent=user_agent,
            details=details or {}
        )
        logger.info(f"Audit log created: {action} by user {user.id if user else 'anonymous'}")
        return audit_log
    except Exception as e:
        logger.error(f"Failed to create audit log: {e}")
        return None


# ==================== UTILITY FUNCTIONS ====================

def generate_unique_admin_id():
    """Generate a unique admin ID for new admin accounts"""
    import random
    import string
    
    while True:
        # Format: ADM-XXXX-YYYY where X is letters and Y is numbers
        letters = ''.join(random.choices(string.ascii_uppercase, k=4))
        numbers = ''.join(random.choices(string.digits, k=4))
        admin_id = f"ADM-{letters}-{numbers}"
        
        # Check if unique
        from .models import User
        if not User.objects.filter(admin_id=admin_id).exists():
            return admin_id


def get_user_by_identifier(identifier):
    """
    Get user by email or TSC number
    
    Args:
        identifier: Email address or TSC number
    
    Returns:
        User object or None
    """
    from .models import User
    
    identifier = identifier.strip().lower()
    
    if '@' in identifier:
        return User.objects.filter(email=identifier).first()
    else:
        return User.objects.filter(tsc_number=identifier).first()


def format_phone_number(phone):
    """Format phone number to standard format"""
    if not phone:
        return ''
    
    # Remove any non-digit characters
    phone = re.sub(r'\D', '', phone)
    
    # Format as 07XX XXX XXX
    if len(phone) == 10 and phone.startswith('07'):
        return f"{phone[:3]} {phone[3:6]} {phone[6:]}"
    elif len(phone) == 9 and phone.startswith('7'):
        return f"0{phone[:2]} {phone[2:5]} {phone[5:]}"
    
    return phone