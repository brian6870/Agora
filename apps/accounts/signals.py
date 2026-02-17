# apps/accounts/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

User = get_user_model()

@receiver(post_save, sender=User)
def user_post_save(sender, instance, created, **kwargs):
    """
    Handle post-save signals for User model
    """
    if created:
        logger.info(f"New user registered: {instance.tsc_number}")
        
        # Send welcome email (if email configured)
        if settings.EMAIL_HOST_USER:
            try:
                send_mail(
                    subject='Welcome to Agora Voting Platform',
                    message=f'Dear {instance.full_name},\n\nThank you for registering on the Agora Voting Platform. Your KYC documents are pending verification.',
                    from_email=settings.EMAIL_HOST_USER,
                    recipient_list=[instance.email] if hasattr(instance, 'email') and instance.email else [],
                    fail_silently=True,
                )
            except Exception as e:
                logger.error(f"Failed to send welcome email: {e}")

@receiver(pre_save, sender=User)
def user_pre_save(sender, instance, **kwargs):
    """
    Handle pre-save signals for User model
    """
    if instance.pk:
        try:
            old_instance = User.objects.get(pk=instance.pk)
            
            # Log KYC status changes
            if old_instance.kyc_status != instance.kyc_status:
                logger.info(f"User {instance.tsc_number} KYC status changed from {old_instance.kyc_status} to {instance.kyc_status}")
                
                # Send notification on KYC verification
                if instance.kyc_status == 'VERIFIED' and settings.EMAIL_HOST_USER:
                    try:
                        send_mail(
                            subject='KYC Verification Approved',
                            message=f'Dear {instance.full_name},\n\nYour KYC verification has been approved. You can now vote when voting opens.',
                            from_email=settings.EMAIL_HOST_USER,
                            recipient_list=[instance.email] if hasattr(instance, 'email') and instance.email else [],
                            fail_silently=True,
                        )
                    except Exception as e:
                        logger.error(f"Failed to send KYC approval email: {e}")
            
            # Log voting status changes
            if old_instance.has_voted != instance.has_voted and instance.has_voted:
                logger.info(f"User {instance.tsc_number} has cast their vote")
                
        except User.DoesNotExist:
            pass