from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import RedirectView
from apps.accounts.views import LandingPageView

urlpatterns = [
    # Admin site (Django built-in)
    path('django-admin/', admin.site.urls),
    
    # Landing page
    path('', LandingPageView.as_view(), name='landing'),
    
    # Account management
    path('accounts/', include('apps.accounts.urls')),
    
    # Core functionality (includes voter dashboard, voting, results, applications)
    path('', include('apps.core.urls')),  # This now includes all voter URLs
    
    # Admin panel (admin users only)
    path('admin-panel/', include('apps.admin_panel.urls')),
    
    # API endpoints (optional - for future use)
    # path('api/', include('apps.api.urls')),
    
    # Favicon redirect
    path('favicon.ico', RedirectView.as_view(url='/static/images/favicon.ico')),
]

# Serve static and media files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0] if settings.STATICFILES_DIRS else settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # In production, you might want to serve static files differently
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Custom error handlers (optional)
handler404 = 'apps.core.views.custom_404'
handler500 = 'apps.core.views.custom_500'
handler403 = 'apps.core.views.custom_403'
handler400 = 'apps.core.views.custom_400'