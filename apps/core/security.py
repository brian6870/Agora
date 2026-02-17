
# apps/core/security.py
import hashlib
import hmac
import secrets
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
import re

class SecurityManager:
    """Centralized security management"""
    
    @staticmethod
    def generate_device_fingerprint(request):
        """Generate unique device fingerprint"""
        components = [
            request.META.get('HTTP_USER_AGENT', ''),
            request.META.get('HTTP_ACCEPT_LANGUAGE', ''),
            request.META.get('HTTP_ACCEPT_ENCODING', ''),
            request.META.get('REMOTE_ADDR', ''),
        ]
        
        # Add screen resolution if available via JavaScript (will be added client-side)
        if request.session.get('screen_resolution'):
            components.append(request.session['screen_resolution'])
        
        fingerprint_string = '|'.join(components)
        return hashlib.sha256(fingerprint_string.encode()).hexdigest()
    
    @staticmethod
    def validate_file_upload(uploaded_file):
        """Validate uploaded files for security"""
        # Check file size
        if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
            return False, "File too large"
        
        # Check file extension
        ext = uploaded_file.name.split('.')[-1].lower()
        if ext not in ['jpg', 'jpeg', 'png', 'gif']:
            return False, "Invalid file type"
        
        # Check file content (basic magic number check)
        try:
            header = uploaded_file.read(4)
            uploaded_file.seek(0)
            
            # JPEG
            if header[:2] == b'\xff\xd8':
                return True, "Valid"
            # PNG
            elif header[:4] == b'\x89PNG':
                return True, "Valid"
            # GIF
            elif header[:3] == b'GIF':
                return True, "Valid"
            else:
                return False, "Invalid image file"
        except:
            return False, "Could not validate file"
    
    @staticmethod
    def sanitize_input(input_string):
        """Sanitize user input"""
        if not input_string:
            return input_string
        
        # Remove potentially dangerous characters
        dangerous_patterns = [
            r'<script.*?>.*?</script>',  # Script tags
            r'on\w+\s*=',                  # Event handlers
            r'javascript:',                 # JavaScript protocol
            r'vbscript:',                   # VBScript protocol
            r'data:',                       # Data protocol
        ]
        
        sanitized = input_string
        for pattern in dangerous_patterns:
            sanitized = re.sub(pattern, '', sanitized, flags=re.IGNORECASE | re.DOTALL)
        
        return sanitized
    
    @staticmethod
    def generate_vote_hash(voter_id, candidate_ids, timestamp):
        """Generate cryptographic hash of vote for audit"""
        data = f"{voter_id}|{sorted(candidate_ids)}|{timestamp}|{settings.SECRET_KEY}"
        return hashlib.sha512(data.encode()).hexdigest()
    
    @staticmethod
    def check_rate_limit(key, limit, period=60):
        """Check rate limit using cache"""
        cache_key = f"rate_limit:{key}"
        attempts = cache.get(cache_key, 0)
        
        if attempts >= limit:
            return False
        
        cache.set(cache_key, attempts + 1, period)
        return True
    
    @staticmethod
    def log_security_event(event_type, request, user=None, extra_data=None):
        """Log security events for audit"""
        from .models import SecurityLog
        
        SecurityLog.objects.create(
            event_type=event_type,
            user=user,
            ip_address=SecurityManager.get_client_ip(request),
            user_agent=request.META.get('HTTP_USER_AGENT', ''),
            path=request.path,
            extra_data=extra_data or {}
        )
    
    @staticmethod
    def get_client_ip(request):
        """Get real client IP"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0]
        return request.META.get('REMOTE_ADDR', '')

# apps/core/middleware.py (additional security middleware)

class SecurityHeadersMiddleware:
    """Add security headers to responses"""
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        response = self.get_response(request)
        
        # Security headers
        response['X-Content-Type-Options'] = 'nosniff'
        response['X-Frame-Options'] = 'DENY'
        response['X-XSS-Protection'] = '1; mode=block'
        response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        if not settings.DEBUG:
            # HSTS
            response['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
            
            # CSP
            csp_policy = [
                "default-src 'self'",
                "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://code.jquery.com",
                "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
                "img-src 'self' data: https:",
                "font-src 'self' https://cdn.jsdelivr.net",
                "connect-src 'self'",
                "frame-ancestors 'none'",
                "base-uri 'self'",
                "form-action 'self'",
            ]
            response['Content-Security-Policy'] = '; '.join(csp_policy)
        
        return response

class SQLInjectionProtectionMiddleware:
    """Additional SQL injection protection"""
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Check for SQL injection patterns in GET/POST data
        dangerous_patterns = [
            r'(\bSELECT\b.*\bFROM\b)',
            r'(\bINSERT\b.*\bINTO\b)',
            r'(\bUPDATE\b.*\bSET\b)',
            r'(\bDELETE\b.*\bFROM\b)',
            r'(\bDROP\b.*\bTABLE\b)',
            r'(\bUNION\b.*\bSELECT\b)',
            r'(\bOR\b.*=.*;)',
            r'(\bAND\b.*=.*;)',
            r'--',
            r';',
        ]
        
        for key, value in request.GET.items():
            if isinstance(value, str):
                for pattern in dangerous_patterns:
                    if re.search(pattern, value, re.IGNORECASE):
                        SecurityManager.log_security_event(
                            'SQL_INJECTION_ATTEMPT',
                            request,
                            extra_data={'parameter': key, 'value': value[:100]}
                        )
                        return HttpResponseForbidden("Invalid request")
        
        response = self.get_response(request)
        return response