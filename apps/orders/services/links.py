"""Link lacak bertoken (docs/02 §10): `/lacak/<kode>/?t=<token>`, berlaku 30 hari."""
from datetime import timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.core import signing

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
