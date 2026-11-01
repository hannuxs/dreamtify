import logging
import mimetypes
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import redirect
from django.templatetags.static import static
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


def favicon(request):
    return redirect(static("img/favicon.ico"), permanent=True)


PUBLIC_TYPES = {".jpg", ".jpeg", ".png", ".webp"}


@require_GET
def public_media(request, path):
    """`/media/public/<path>` — poster & gambar publik, dengan cache header.
    File privat TIDAK pernah lewat sini (docs/09 §4)."""
    root = Path(settings.PUBLIC_MEDIA_ROOT).resolve()
    target = (root / path).resolve()
    if root not in target.parents or target.suffix.lower() not in PUBLIC_TYPES or not target.is_file():
        raise Http404
    response = FileResponse(target.open("rb"), content_type=mimetypes.guess_type(target.name)[0])
    response["Cache-Control"] = "public, max-age=86400"
    response["X-Content-Type-Options"] = "nosniff"
    return response
