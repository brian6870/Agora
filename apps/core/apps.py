# apps/core/apps.py
from django.apps import AppConfig

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.core'
    verbose_name = 'Core Functionality'
    
    def ready(self):
        # Import signals only if the module exists
        try:
            import apps.core.signals
        except ImportError:
            pass  # Signals file not created yet