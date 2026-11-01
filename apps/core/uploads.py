"""
File upload (docs/09 §4).

- Lokasi: media/private/<tahun>/<bulan>/<uuid>.<ext> (bukti transfer, e-tiket, dsb.)
  atau media/public/… (poster, testimoni yang disetujui). Nama file selalu UUID.
- Validasi berdasarkan ISI (Pillow verify / header %PDF-), bukan ekstensi. Maks 10 MB.
- Gambar disimpan ulang (EXIF/lokasi terbuang), lebar dibatasi, format JPEG.
"""
import io
import uuid
from pathlib import Path

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PRIVATE_MAX_WIDTH = 2000
PUBLIC_MAX_WIDTH = 1600
ACCEPT_ATTR = "image/jpeg,image/png,image/webp,application/pdf"
IMAGE_ACCEPT_ATTR = "image/jpeg,image/png,image/webp"


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


def _read(upload) -> bytes:
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Ukuran file maksimal 10 MB.", code="too_large")
    upload.seek(0)
    data = upload.read()
    if len(data) > MAX_UPLOAD_BYTES:
        raise ValidationError("Ukuran file maksimal 10 MB.", code="too_large")
    return data


def reencode_image(data: bytes, *, max_width: int, name: str) -> ContentFile:
    """Validasi isi gambar, putar sesuai EXIF, buang metadata, perkecil, simpan JPEG."""
    if data[4:12] in (b"ftypheic", b"ftypheix", b"ftypmif1", b"ftyphevc"):
        raise ValidationError("Format HEIC (foto iPhone) belum didukung. Kirim screenshot atau JPG ya, kak.",
                              code="heic")
    try:
        Image.open(io.BytesIO(data)).verify()
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise ValidationError("File bukan gambar yang valid. Pakai JPG, PNG, WEBP, atau PDF.",
                              code="invalid_image") from exc
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        background = Image.new("RGB", img.size, (255, 255, 255))
        background.paste(img, mask=img.getchannel("A"))
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")
    if img.width > max_width:
        img = img.resize((max_width, round(img.height * max_width / img.width)), Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=85, optimize=True, progressive=True)  # tanpa EXIF
    return ContentFile(out.getvalue(), name=f"{name}.jpg")


def process_private_upload(upload, *, name: str = "berkas") -> ContentFile:
    """Bukti transfer / e-tiket / foto: gambar (diproses ulang) atau PDF."""
    data = _read(upload)
    if data.startswith(b"%PDF-"):
        if b"%%EOF" not in data[-2048:]:
            raise ValidationError("File PDF rusak atau tidak lengkap.", code="invalid_pdf")
        return ContentFile(data, name=f"{name}.pdf")
    return reencode_image(data, max_width=PRIVATE_MAX_WIDTH, name=name)


def process_public_image(upload, *, max_width: int = PUBLIC_MAX_WIDTH, name: str = "gambar") -> ContentFile:
    """Poster & gambar publik: hanya gambar."""
    return reencode_image(_read(upload), max_width=max_width, name=name)
