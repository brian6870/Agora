import os
import sys
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Add the project directory to Python path
sys.path.append(str(BASE_DIR))

# Try to import decouple, but if it fails, use a simple environment variable fallback
try:
    from decouple import config, Csv
    USING_DECOUPLE = True
except ImportError:
    # Simple fallback for when decouple is not available
    USING_DECOUPLE = False
    
    def config(key, default=None, cast=None):
        """Fallback config function when python-decouple is not installed"""
        value = os.environ.get(key)
        if value is None:
            return default
        if cast == bool:
            return value.lower() in ('true', '1', 'yes', 'on', 't')
        if cast == int:
            try:
                return int(value)
            except (ValueError, TypeError):
                return default
        if cast == float:
            try:
                return float(value)
            except (ValueError, TypeError):
                return default
        return value
    
    def Csv(cast=None):
        """Fallback Csv function when python-decouple is not installed"""
        def parse(value):
            if value is None:
                return []
            if isinstance(value, (list, tuple)):
                return value
            items = [x.strip() for x in str(value).split(',') if x.strip()]
            if cast:
                return [cast(x) for x in items]
            return items
        return parse

# Initialize environment variables (moved after BASE_DIR is defined)
# Read .env file if it exists
env_file = BASE_DIR / '.env'
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if '=' in line and not line.startswith('#'):
                key, value = line.strip().split('=', 1)
                os.environ.setdefault(key, value)

# Security
SECRET_KEY = config('SECRET_KEY', default='django-insecure-dev-key-change-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1', cast=Csv())

# Application definition
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

# Database Configuration
import dj_database_url

# Default SQLite for development
if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'agora.db',
            'OPTIONS': {
                'timeout': 20,
            }
        }
    }
else:
    # Production database from DATABASE_URL environment variable
    DATABASES = {
        'default': dj_database_url.config(
            default='sqlite:///' + str(BASE_DIR / 'agora.db'),
            conn_max_age=600,
            ssl_require=True
        )
    }

# Custom user model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Login URLs
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'core:dashboard'

# Email settings - Load from environment variables
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@agora.ke')

# Rate limiting settings
OTP_RATE_LIMIT = config('OTP_RATE_LIMIT', default=3, cast=int)
OTP_RATE_LIMIT_PERIOD = config('OTP_RATE_LIMIT_PERIOD', default=86400, cast=int)  # 24 hours in seconds

# Cache settings
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'agora-cache',
    }
}

# Maximum file upload size (10MB)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

# Security headers - Set based on DEBUG
if not DEBUG:
    CSRF_COOKIE_SECURE = True
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
else:
    CSRF_COOKIE_SECURE = False
    SESSION_COOKIE_SECURE = False
    SECURE_SSL_REDIRECT = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'

# CSRF trusted origins
CSRF_TRUSTED_ORIGINS = os.environ.get('CSRF_TRUSTED_ORIGINS', '').split(',')
if not CSRF_TRUSTED_ORIGINS or CSRF_TRUSTED_ORIGINS == ['']:
    CSRF_TRUSTED_ORIGINS = [
        'http://localhost:8000',
        'http://127.0.0.1:8000',
    ]
    # Add your production domain when DEBUG=False
    if not DEBUG:
        CSRF_TRUSTED_ORIGINS.append('https://agora-86ue.onrender.com')  # Update with your actual domain

# MIME types for development
if DEBUG:
    import mimetypes
    mimetypes.add_type("application/javascript", ".js", True)

# Logging configuration
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
if not logs_dir.exists():
    logs_dir.mkdir(parents=True, exist_ok=True)

# Print configuration status for debugging
if DEBUG:
    print("\n" + "="*50)
    print("AGORA CONFIGURATION")
    print("="*50)
    print(f"Using python-decouple: {USING_DECOUPLE}")
    print(f"DEBUG: {DEBUG}")
    print(f"Database: {DATABASES['default']['NAME']}")
    print(f"Email Host: {EMAIL_HOST or 'Not configured'}")
    print(f"OTP Rate Limit: {OTP_RATE_LIMIT} per {OTP_RATE_LIMIT_PERIOD//3600} hours")
    print("="*50 + "\n")