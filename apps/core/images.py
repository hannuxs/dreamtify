"""Kompatibilitas: pemrosesan gambar ada di `apps.core.uploads`."""
from .uploads import MAX_UPLOAD_BYTES, PUBLIC_MAX_WIDTH, process_public_image

__all__ = ["MAX_UPLOAD_BYTES", "PUBLIC_MAX_WIDTH", "process_public_image"]
