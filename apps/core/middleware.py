"""Header keamanan semua respons (docs/09 §7)."""
from django.conf import settings

# Tanpa 'unsafe-inline'/'unsafe-eval': Alpine memakai build CSP, HTMX dengan allowEval=false.
# img data: untuk pratinjau upload (FileReader).
CONTENT_SECURITY_POLICY = "; ".join((
    "default-src 'self'",
    "script-src 'self'",
    "style-src 'self'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
))
PERMISSIONS_POLICY = "camera=(), microphone=(), geolocation=(), payment=()"


class SecurityHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Halaman debug Django butuh gaya inline
        if not (settings.DEBUG and response.status_code >= 500):
            response.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.setdefault("Permissions-Policy", PERMISSIONS_POLICY)
        return response
