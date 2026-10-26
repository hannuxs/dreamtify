"""Kode pesanan `DRM-XXXXXX` (docs/02 §10) dan kode unik nominal (§4.1)."""
import secrets

from apps.core.enums import OrderStatus

ALPHABET = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"  # tanpa 0/O, 1/I/L yang mudah tertukar
PREFIX = "DRM-"
LENGTH = 6
UNIQUE_CODE_MAX = 499


def generate_code() -> str:
    return PREFIX + "".join(secrets.choice(ALPHABET) for _ in range(LENGTH))


def new_order_code(max_attempts: int = 20) -> str:
    """Kode yang belum dipakai. Bentrok sangat jarang (31^6 ≈ 887 juta kombinasi);
    pemanggil tetap menangani IntegrityError karena unique constraint di DB."""
    from apps.orders.models import Order

    for _ in range(max_attempts):
        code = generate_code()
        if not Order.objects.filter(code=code).exists():
            return code
    raise RuntimeError("Gagal membuat kode pesanan unik.")


def normalize_code(raw: str) -> str:
    """'drm-abc234' / 'ABC234' → 'DRM-ABC234'."""
    cleaned = "".join(ch for ch in (raw or "").upper() if ch.isalnum())
    if cleaned.startswith("DRM"):
        cleaned = cleaned[3:]
    return PREFIX + cleaned


def pick_unique_code(event, exclude_order_id=None):
    """Angka 1–499 yang belum dipakai pesanan MENUNGGU_FEE event ini; None bila habis."""
    from apps.orders.models import Order

    used = set(
        Order.objects.filter(event=event, status=OrderStatus.MENUNGGU_FEE, unique_code__isnull=False)
        .exclude(pk=exclude_order_id)
        .values_list("unique_code", flat=True)
    )
    available = [n for n in range(1, UNIQUE_CODE_MAX + 1) if n not in used]
    return secrets.choice(available) if available else None
