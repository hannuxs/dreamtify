"""Nomor WhatsApp Indonesia: validasi & normalisasi ke format `62…` (docs/09 §8)."""
import re

from django.core.exceptions import ValidationError

_WA_RE = re.compile(r"^(\+?62|0)8[0-9]{7,12}$")
_SEPARATORS = re.compile(r"[\s\-.()]")


def is_valid_wa(raw: str) -> bool:
    return bool(_WA_RE.match(_SEPARATORS.sub("", raw or "")))


def normalize_wa(raw: str) -> str:
    """'0812-3456-7890' / '+62 812…' / '62812…' → '62812…'. Tidak valid → ValidationError."""
    cleaned = _SEPARATORS.sub("", raw or "")
    if not _WA_RE.match(cleaned):
        raise ValidationError("Nomor WhatsApp tidak valid. Contoh: 0812 3456 7890.", code="invalid_wa")
    if cleaned.startswith("+"):
        cleaned = cleaned[1:]
    if cleaned.startswith("0"):
        cleaned = "62" + cleaned[1:]
    return cleaned


def to_local(wa: str) -> str:
    """'62812…' → '0812…' (format yang dikenal promotor)."""
    if wa and wa.startswith("62"):
        return "0" + wa[2:]
    return wa or ""


def validate_wa(value: str) -> None:
    normalize_wa(value)
