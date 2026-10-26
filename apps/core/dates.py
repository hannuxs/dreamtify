"""Format tanggal untuk teks customer (WIB / TIME_ZONE dari .env)."""
from django.utils import dateformat, timezone, translation


def format_local(dt, fmt: str = "D, j M Y H.i") -> str:
    """datetime aware → 'Sen, 14 Sep 2026 19.00 WIB'. None → ''."""
    if not dt:
        return ""
    with translation.override("id"):
        text = dateformat.format(timezone.localtime(dt), fmt)
    return f"{text} {timezone_label()}"


def timezone_label() -> str:
    name = timezone.get_current_timezone_name()
    return {"Asia/Jakarta": "WIB", "Asia/Makassar": "WITA", "Asia/Jayapura": "WIT"}.get(name, name)
