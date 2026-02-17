# apps/voting/apps.py
from django.apps import AppConfig

class VotingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.voting'
    verbose_name = 'Voting Management'
    
    def ready(self):
        pass  # No signals needed