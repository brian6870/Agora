from celery import shared_task
from django.core.management import call_command
import logging

logger = logging.getLogger(__name__)

@shared_task
def process_elections():
    """Celery task to process election transitions"""
    try:
        call_command('process_elections')
        logger.info("Election processing task completed successfully")
    except Exception as e:
        logger.error(f"Election processing task failed: {e}")