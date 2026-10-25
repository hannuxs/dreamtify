import logging

from django.db import connection
from django.http import JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@never_cache
@require_GET
def health(request):
    """`/sehat/` — health check untuk installer & pemantauan (cek koneksi DB)."""
    db_ok = True
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        db_ok = False
        logger.exception("Health check: koneksi database gagal")
    return JsonResponse(
        {"status": "ok" if db_ok else "error", "db": db_ok},
        status=200 if db_ok else 503,
    )
