# apps/accounts/apps.py
from django.apps import AppConfig

class AccountsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.accounts'
    verbose_name = 'Accounts Management'
    
    def ready(self):
        # Import signals only if the module exists
        try:
            import apps.accounts.signals
        except ImportError:
            pass  # Signals file not created yet