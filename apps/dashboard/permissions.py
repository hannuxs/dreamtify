"""
Peran admin (docs/03 "Pengguna & peran"):
- Owner: semua akses (superuser juga dianggap Owner).
- Admin: operasional.
"""
from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied

OWNER = "Owner"
ADMIN = "Admin"


def role_of(user) -> str | None:
    if not getattr(user, "is_authenticated", False) or not user.is_active:
        return None
    cached = getattr(user, "_dt_role", "unset")
    if cached != "unset":
        return cached
    if user.is_superuser:
        role = OWNER
    else:
        names = set(user.groups.values_list("name", flat=True))
        role = OWNER if OWNER in names else ADMIN if ADMIN in names else None
    user._dt_role = role
    return role


def is_owner(user) -> bool:
    return role_of(user) == OWNER


def is_admin(user) -> bool:
    """Owner atau Admin."""
    return role_of(user) is not None


def _guard(check):
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path(), settings.LOGIN_URL)
            if not check(request.user):
                raise PermissionDenied("Halaman ini khusus Owner." if check is is_owner else "Tidak punya akses.")
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


admin_required = _guard(is_admin)
owner_required = _guard(is_owner)
