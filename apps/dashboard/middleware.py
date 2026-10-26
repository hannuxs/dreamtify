"""Logout otomatis admin bila tidak aktif 2 jam (docs/09 §5)."""
import time

from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

IDLE_LIMIT_SECONDS = 2 * 60 * 60
TOUCH_EVERY_SECONDS = 60
SESSION_KEY = "dash_last_seen"


class AdminIdleTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated and request.path.startswith("/kelola/"):
            now = int(time.time())
            last = request.session.get(SESSION_KEY)
            if last and now - last > IDLE_LIMIT_SECONDS:
                logout(request)
                messages.info(request, "Sesi berakhir karena tidak aktif 2 jam. Silakan masuk lagi.")
                return redirect(f"/kelola/login/?next={request.path}")
            if not last or now - last > TOUCH_EVERY_SECONDS:
                request.session[SESSION_KEY] = now
        return self.get_response(request)
