"""
Lokasi file upload. Nama file selalu UUID (docs/09 §4).
Validasi isi, buang EXIF, dsb. ditambahkan di fase 05.
"""
import uuid
from pathlib import Path

from django.utils import timezone


def _path(prefix: str, filename: str) -> str:
    ext = Path(filename or "").suffix.lower()[:8]
    now = timezone.now()
    return f"{prefix}/{now:%Y}/{now:%m}/{uuid.uuid4().hex}{ext}"


def private_upload_to(instance, filename: str) -> str:
    """media/private/<tahun>/<bulan>/<uuid>.<ext> — hanya lewat view berizin."""
    return _path("private", filename)


def public_upload_to(instance, filename: str) -> str:
    """media/public/<tahun>/<bulan>/<uuid>.<ext> — poster, testimoni disetujui."""
    return _path("public", filename)
