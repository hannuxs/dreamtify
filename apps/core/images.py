"""
Gambar publik (poster, logo): validasi isi, buang EXIF, perkecil, simpan ulang
sebagai JPEG (docs/06 §6, docs/09 §4). Upload privat (bukti transfer) di fase 05.
"""
import io

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 10 * 1024 * 1024
PUBLIC_MAX_WIDTH = 1600


def process_public_image(upload, *, max_width: int = PUBLIC_MAX_WIDTH, name: str = "gambar") -> ContentFile:
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Ukuran file maksimal 10 MB.")
    try:
        upload.seek(0)
        Image.open(upload).verify()  # cek isi, bukan ekstensi
        upload.seek(0)
        img = Image.open(upload)
        img.load()
    except (UnidentifiedImageError, OSError, SyntaxError) as exc:
        raise ValidationError("File bukan gambar yang valid (pakai JPG, PNG, atau WEBP).") from exc

    img = ImageOps.exif_transpose(img)  # putar sesuai EXIF, lalu EXIF dibuang saat simpan ulang
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
    img.save(out, format="JPEG", quality=85, optimize=True, progressive=True)
    return ContentFile(out.getvalue(), name=f"{name}.jpg")
