"""
Penyamar data sensitif di log (docs/09 §2).

NIK (16 digit, boleh dipisah spasi/titik/strip) dan deretan angka panjang
(≥10 digit: nomor rekening, nomor WA) tidak boleh tertulis utuh di log.
Yang tersisa hanya 4 digit terakhir.
"""
import logging
import re

# 16 digit dengan pemisah opsional, mis. "3171 0123 4567 8901"
_NIK_RE = re.compile(r"(?<!\d)\d(?:[ .\-]?\d){15}(?!\d)")
# Deretan ≥10 digit tanpa pemisah (rekening, WA, NIK tanpa spasi)
_LONG_DIGITS_RE = re.compile(r"(?<!\d)\d{10,}(?!\d)")


def _mask(match: re.Match) -> str:
    digits = re.sub(r"\D", "", match.group(0))
    return "*" * (len(digits) - 4) + digits[-4:]


def mask_sensitive(text: str) -> str:
    if not text:
        return text
    text = _NIK_RE.sub(_mask, text)
    return _LONG_DIGITS_RE.sub(_mask, text)


class MaskSensitiveFilter(logging.Filter):
    """Menyamarkan pesan log (msg + args) sebelum diteruskan ke handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:  # format pesan rusak: biarkan handler yang melapor
            return True
        masked = mask_sensitive(message)
        if masked != message:
            record.msg = masked
            record.args = None
        return True


class MaskingFormatter(logging.Formatter):
    """Menyamarkan hasil akhir (termasuk traceback) — lapis kedua setelah filter."""

    def format(self, record: logging.LogRecord) -> str:
        return mask_sensitive(super().format(record))
