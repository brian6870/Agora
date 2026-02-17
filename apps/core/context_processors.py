# apps/core/context_processors.py
from apps.core.models import ElectionSettings  # Fixed import - from core.models, not voting.models
from django.utils import timezone

def election_settings(request):
    """
    Context processor to make election settings available in all templates
    """
    try:
        settings = ElectionSettings.get_settings()
    except:
        settings = None
    
    return {
        'election': settings,
        'current_year': timezone.now().year
    }

def device_info(request):
    """
    Context processor to make device info available
    """
    return {
        'device_fingerprint': getattr(request, 'device_fingerprint', None),
        'is_mobile': request.user_agent.is_mobile if hasattr(request, 'user_agent') else False
    }