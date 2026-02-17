from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Election

@receiver(post_save, sender=Election)
def check_election_status_on_save(sender, instance, created, **kwargs):
    """Check if election status should be updated when saved"""
    instance.check_and_update_status()