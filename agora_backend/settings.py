import os
import sys
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Add the project directory to Python path
sys.path.append(str(BASE_DIR))

# ==================== ENVIRONMENT VARIABLES ====================
# Simple environment variable handling
def get_env(key, default=None):
    """Simple environment variable getter"""
    return os.environ.get(key, default)

def get_env_bool(key, default=False):
    """Get boolean from environment"""
    value = os.environ.get(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on', 't')

def get_env_int(key, default=0):
    """Get integer from environment"""
    try:
        return int(os.environ.get(key, default))
    except (ValueError, TypeError):
        return default

def get_env_list(key, default=''):
    """Get list from comma-separated environment variable"""
    value = os.environ.get(key, default)
    if not value:
        return []
    return [item.strip() for item in value.split(',') if item.strip()]

# ==================== CORE SETTINGS ====================
SECRET_KEY = get_env('SECRET_KEY', 'django-insecure-dev-key-change-in-production')
DEBUG = get_env_bool('DEBUG', False)

# ALLOWED_HOSTS - from environment variable
ALLOWED_HOSTS = get_env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1')

# Add Render domain if present in environment
RENDER_EXTERNAL_HOSTNAME = get_env('RENDER_EXTERNAL_HOSTNAME')
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

# Always add common Render pattern
if '.onrender.com' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('.onrender.com')

# ==================== APPLICATION DEFINITION ====================
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    
    # Local apps
    'apps.accounts',
    'apps.voting',
    'apps.admin_panel',
    'apps.core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'apps.core.middleware.DeviceFingerprintMiddleware',
    'apps.core.middleware.MaintenanceModeMiddleware', 
]

ROOT_URLCONF = 'agora_backend.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.static',
                'django.template.context_processors.media',
            ],
        },
    },
]

WSGI_APPLICATION = 'agora_backend.wsgi.application'

# ==================== DATABASE ====================
import dj_database_url

if DEBUG:
    # Development: SQLite - NO SSL MODE
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'agora.db',
        }
    }
else:
    # Production: PostgreSQL from DATABASE_URL
    # Get the database URL from environment
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and database_url.startswith('postgres'):
        # PostgreSQL - with SSL
        DATABASES = {
            'default': dj_database_url.config(
                conn_max_age=600,
                ssl_require=True  # This adds sslmode=require for PostgreSQL
            )
        }
    else:
        # Fallback to SQLite if no PostgreSQL URL (shouldn't happen on Render)
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'agora.db',
            }
        }
        print("⚠️ WARNING: Using SQLite in production! Set DATABASE_URL for PostgreSQL.")

# ==================== AUTHENTICATION ====================
AUTH_USER_MODEL = 'accounts.User'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:dashboard'

# ==================== INTERNATIONALIZATION ====================
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# ==================== STATIC & MEDIA FILES ====================
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# ==================== EMAIL SETTINGS ====================
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = get_env('EMAIL_HOST', '')
EMAIL_PORT = get_env_int('EMAIL_PORT', 587)
EMAIL_USE_TLS = get_env_bool('EMAIL_USE_TLS', True)
EMAIL_USE_SSL = get_env_bool('EMAIL_USE_SSL', False)
EMAIL_HOST_USER = get_env('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = get_env('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = get_env('DEFAULT_FROM_EMAIL', 'noreply@agora.ke')

# ==================== RATE LIMITING ====================
OTP_RATE_LIMIT = get_env_int('OTP_RATE_LIMIT', 3)
OTP_RATE_LIMIT_PERIOD = get_env_int('OTP_RATE_LIMIT_PERIOD', 86400)  # 24 hours

# ==================== CACHE ====================
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'agora-cache',
    }
}

# ==================== SECURITY SETTINGS ====================
# Security headers from environment (with production defaults)
SESSION_COOKIE_SECURE = get_env_bool('SESSION_COOKIE_SECURE', not DEBUG)
CSRF_COOKIE_SECURE = get_env_bool('CSRF_COOKIE_SECURE', not DEBUG)
SECURE_SSL_REDIRECT = get_env_bool('SECURE_SSL_REDIRECT', not DEBUG)

# HSTS settings
SECURE_HSTS_SECONDS = get_env_int('SECURE_HSTS_SECONDS', 31536000 if not DEBUG else 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = get_env_bool('SECURE_HSTS_INCLUDE_SUBDOMAINS', not DEBUG)
SECURE_HSTS_PRELOAD = get_env_bool('SECURE_HSTS_PRELOAD', not DEBUG)

# Always-on security headers
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# ==================== CSRF TRUSTED ORIGINS ====================
CSRF_TRUSTED_ORIGINS = get_env_list('CSRF_TRUSTED_ORIGINS', '')

# Auto-generate CSRF trusted origins from ALLOWED_HOSTS if not set
if not CSRF_TRUSTED_ORIGINS:
    CSRF_TRUSTED_ORIGINS = []
    for host in ALLOWED_HOSTS:
        if host.startswith('.'):
            # For wildcard subdomains like .onrender.com
            CSRF_TRUSTED_ORIGINS.append(f'https://{host.lstrip(".")}')
            CSRF_TRUSTED_ORIGINS.append(f'https://*{host}')
        elif host not in ['localhost', '127.0.0.1']:
            CSRF_TRUSTED_ORIGINS.append(f'https://{host}')
    
    # Always add localhost for development
    CSRF_TRUSTED_ORIGINS.extend([
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ])

# ==================== FILE UPLOADS ====================
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10MB

# ==================== LOGGING ====================
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': str(BASE_DIR / 'logs' / 'django.log'),
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}

# Create logs directory if it doesn't exist
logs_dir = BASE_DIR / 'logs'
logs_dir.mkdir(parents=True, exist_ok=True)

# ==================== DEBUG OUTPUT ====================
print("\n" + "="*60)
print("🚀 AGORA VOTING SYSTEM CONFIGURATION")
print("="*60)
print(f"🔧 DEBUG Mode: {DEBUG}")
print(f"🌐 ALLOWED_HOSTS: {ALLOWED_HOSTS}")
print(f"🔒 CSRF_TRUSTED_ORIGINS: {CSRF_TRUSTED_ORIGINS}")
print(f"🗄️ Database: {'PostgreSQL' if not DEBUG else 'SQLite'}")
print(f"📧 Email Host: {EMAIL_HOST}")
print(f"📧 Email User: {EMAIL_HOST_USER}")
print(f"🔐 SESSION_COOKIE_SECURE: {SESSION_COOKIE_SECURE}")
print(f"🔐 CSRF_COOKIE_SECURE: {CSRF_COOKIE_SECURE}")
print(f"🔐 SECURE_SSL_REDIRECT: {SECURE_SSL_REDIRECT}")
print(f"⏱️  OTP Rate Limit: {OTP_RATE_LIMIT} per {OTP_RATE_LIMIT_PERIOD//3600} hours")
print("="*60 + "\n")