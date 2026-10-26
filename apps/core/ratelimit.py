"""
Rate limit sederhana di atas cache Django (DatabaseCache, tanpa Redis) — docs/09 §6.

Jendela tetap: hitungan dimulai saat percobaan pertama dan kedaluwarsa setelah
`window` detik. IP diambil dari REMOTE_ADDR, atau X-Forwarded-For hanya bila
TRUSTED_PROXY=1 di .env.
"""
import hashlib

from django.conf import settings
from django.core.cache import cache


def client_ip(request) -> str:
    if settings.TRUSTED_PROXY:
        forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "") or "0.0.0.0"


def _key(scope: str, ident: str) -> str:
    return f"rl:{scope}:{hashlib.sha256(ident.encode()).hexdigest()[:40]}"


def hit(scope: str, ident: str, limit: int, window: int) -> bool:
    """Catat satu percobaan. True = masih diizinkan (hitungan ≤ limit)."""
    key = _key(scope, ident)
    if cache.add(key, 1, window):
        return 1 <= limit
    try:
        count = cache.incr(key)
    except ValueError:  # kedaluwarsa di antara add & incr
        cache.set(key, 1, window)
        count = 1
    return count <= limit


def count(scope: str, ident: str) -> int:
    return cache.get(_key(scope, ident), 0)


def is_blocked(scope: str, ident: str, limit: int) -> bool:
    return count(scope, ident) >= limit


def reset(scope: str, ident: str) -> None:
    cache.delete(_key(scope, ident))
