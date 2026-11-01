"""Link lacak bertoken (docs/02 §10): `/lacak/<kode>/?t=<token>`, berlaku 30 hari."""
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing

from apps.core.enums import EventStatus

TOKEN_SALT = "dreamtify.lacak"
TOKEN_MAX_AGE = timedelta(days=30)


def make_tracking_token(order) -> str:
    return signing.dumps(order.code, salt=TOKEN_SALT, compress=True)


def check_tracking_token(code: str, token: str) -> bool:
    """True bila token sah, belum kedaluwarsa, dan milik kode ini."""
    try:
        value = signing.loads(token, salt=TOKEN_SALT, max_age=TOKEN_MAX_AGE)
    except signing.BadSignature:  # termasuk SignatureExpired
        return False
    return value == code


def tracking_path(order) -> str:
    return f"/lacak/{order.code}/?{urlencode({'t': make_tracking_token(order)})}"


def tracking_url(order) -> str:
    return settings.SITE_URL + tracking_path(order)


def _file_salt(event) -> str:
    # Tanda tangan ikut mati bila link promotor diganti (token baru)
    return f"dreamtify.berkas.promotor:{event.promotor_token}"


def promotor_file_signature(event, kind: str, pk: int) -> str:
    """Tanda tangan link berkas untuk ekspor promotor (docs/07 §3)."""
    return signing.dumps(f"{kind}:{pk}", salt=_file_salt(event), compress=True)


def promotor_proof_url(event, payment) -> str:
    query = urlencode({"s": promotor_file_signature(event, "bukti", payment.pk)})
    return f"{settings.SITE_URL}/p/{event.promotor_token}/bukti/{payment.pk}/?{query}"


def check_promotor_file_signature(event, kind: str, pk: int, signature: str) -> bool:
    # ASUMSI (docs/07 §3): berlaku selama token sama & event belum diarsip, walau halaman link dinonaktifkan,
    # agar link di Excel yang diunduh admin tetap terbuka. Untuk mematikannya: ganti link.
    if not signature or event.status == EventStatus.ARSIP:
        return False
    try:
        return signing.loads(signature, salt=_file_salt(event)) == f"{kind}:{pk}"
    except signing.BadSignature:
        return False
