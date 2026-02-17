# apps/core/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.core.cache import cache
from .models import ElectionSettings, DeviceResetRequest
from apps.voting.models import Vote
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Vote)
def vote_post_save(sender, instance, created, **kwargs):
    """
    Update election statistics when a vote is cast
    """
    if created:
        try:
            settings = ElectionSettings.get_settings()
            settings.total_votes_cast += 1
            settings.save()
            
            # Clear cached results
            cache.delete('election_results')
            cache.delete('voting_statistics')
            
            logger.info(f"Vote recorded. Total votes: {settings.total_votes_cast}")
        except Exception as e:
            logger.error(f"Error updating vote statistics: {e}")

@receiver(post_save, sender=DeviceResetRequest)
def device_reset_post_save(sender, instance, created, **kwargs):
    """
    Log device reset requests
    """
    if created:
        logger.info(f"New device reset request from {instance.tsc_number}")
    elif instance.status == 'APPROVED':
        logger.info(f"Device reset approved for {instance.tsc_number}")
    elif instance.status == 'REJECTED':
        logger.info(f"Device reset rejected for {instance.tsc_number}: {instance.rejection_reason}")

@receiver(post_delete, sender=Vote)
def vote_post_delete(sender, instance, **kwargs):
    """
    Update statistics when a vote is deleted (audit purposes)
    """
    try:
        settings = ElectionSettings.get_settings()
        if settings.total_votes_cast > 0:
            settings.total_votes_cast -= 1
            settings.save()
        
        cache.delete('election_results')
        logger.warning(f"Vote deleted for user {instance.voter.tsc_number}")
    except Exception as e:
        logger.error(f"Error updating vote statistics on delete: {e}")