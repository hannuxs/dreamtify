from django import template
from django.templatetags.static import static
from django.utils.html import format_html

from apps.core.enums import OrderStatus, SlotResult
from apps.core.money import format_rupiah

register = template.Library()

# Warna badge status pesanan (docs/06 §4)
STATUS_TONES = {
    OrderStatus.WAITING_LIST: "neutral",
    OrderStatus.MENUNGGU_FEE: "warning",
    OrderStatus.MENUNGGU_PELUNASAN: "warning",
    OrderStatus.VERIFIKASI_FEE: "info",
    OrderStatus.VERIFIKASI_PELUNASAN: "info",
    OrderStatus.SIAP_WAR: "navy",
    OrderStatus.PROSES_WAR: "live",
    OrderStatus.PENYELESAIAN: "sky",
    OrderStatus.SELESAI: "success",
    OrderStatus.DIBATALKAN: "danger",
    OrderStatus.HANGUS: "danger",
}
RESULT_TONES = {
    SlotResult.MENUNGGU: "neutral",
    SlotResult.SECURED: "success",
    SlotResult.GAGAL: "danger",
    SlotResult.GAGAL_CUSTOMER: "danger",
}


@register.filter
def rupiah(value):
    """{{ 1250000|rupiah }} → Rp 1.250.000"""
    try:
        return format_rupiah(value)
    except (TypeError, ValueError):
        return ""


@register.filter
def status_tone(status):
    return STATUS_TONES.get(status, "neutral")


@register.filter
def result_tone(result):
    return RESULT_TONES.get(result, "neutral")


@register.simple_tag
def icon(name, cls="", label=""):
    """Ikon dari sprite `static/img/icons.svg`.

    {% icon "copy" %} — dekoratif (aria-hidden).
    {% icon "x" label="Tutup" %} — diberi nama aksesibel.
    """
    href = f"{static('img/icons.svg')}#{name}"
    css = f"icon {cls}".strip()
    if label:
        return format_html(
            '<svg class="{}" role="img" aria-label="{}"><use href="{}"></use></svg>', css, label, href
        )
    return format_html(
        '<svg class="{}" aria-hidden="true" focusable="false"><use href="{}"></use></svg>', css, href
    )
