"""
Akses customer ke pesanan (docs/02 §10): kode + WA → izin di session 12 jam,
atau link bertoken `?t=` (30 hari). Setiap view pesanan memeriksa izin untuk
KODE ITU (customer A tidak bisa membuka pesanan B).
"""
import time

from apps.dashboard.permissions import is_admin
from apps.orders.services.links import check_tracking_token

SESSION_KEY = "lacak_access"
SESSION_MY_ORDERS = "my_orders"  # diisi saat pesanan dibuat dari browser ini
ACCESS_SECONDS = 12 * 60 * 60


def grant(request, code: str) -> None:
    access = {c: exp for c, exp in request.session.get(SESSION_KEY, {}).items() if exp > time.time()}
    access[code] = int(time.time()) + ACCESS_SECONDS
    request.session[SESSION_KEY] = access


def has_access(request, code: str) -> bool:
    """Cek izin; token sah di URL langsung dicatat ke session agar POST berikutnya tidak perlu token."""
    exp = request.session.get(SESSION_KEY, {}).get(code)
    if exp and exp > time.time():
        return True
    if code in request.session.get(SESSION_MY_ORDERS, []):
        return True
    token = request.GET.get("t", "")
    if token and check_tracking_token(code, token):
        grant(request, code)
        return True
    return is_admin(request.user)
