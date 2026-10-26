"""
Antrian kabar (docs/08). Versi fase 02: membuat baris Notification WA
(dikirim manual dari Kotak Kabar) dan EMAIL (bila diaktifkan; pengiriman
otomatis dibangun di fase 09). `dedupe_key` mencegah kabar ganda.
"""
import re

from django.db import IntegrityError, transaction

from apps.core.dates import format_local
from apps.core.enums import NotificationChannel, NotificationStatus, SlotResult
from apps.core.models import BankAccount, SiteSetting
from apps.core.money import format_rupiah

from .defaults import DEFAULT_TEMPLATES, EMAIL_ONLY_KEYS, WA_ONLY_KEYS
from .models import MessageTemplate, Notification

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")


def render(body: str, context: dict) -> str:
    """Ganti {placeholder} yang dikenal; yang tidak dikenal dibiarkan apa adanya."""
    return _PLACEHOLDER.sub(lambda m: str(context.get(m.group(1), m.group(0))), body)


def _ticket_summary(order) -> str:
    rows = []
    for line in order.lines.all():
        cats = " / ".join(c.name for c in (line.cat_primary, line.cat_backup1, line.cat_backup2) if c)
        rows.append(f"• {line.holder_name} · {line.service_type} · {line.quantity} tiket · {cats}")
    return "\n".join(rows)


def _result_summary(order) -> str:
    rows = []
    for line in order.lines.all():
        for slot in line.slots.all():
            if slot.result == SlotResult.SECURED:
                rows.append(f"✅ {slot.secured_category.name} a.n. {line.holder_name}")
            elif slot.result == SlotResult.MENUNGGU:
                rows.append(f"⏳ Menunggu a.n. {line.holder_name}")
            else:
                rows.append(f"❌ Tidak dapat a.n. {line.holder_name}")
    return "\n".join(rows)


def build_context(order, extra: dict | None = None) -> dict:
    from apps.orders.services.links import tracking_url

    site = SiteSetting.load()
    accounts = BankAccount.objects.filter(is_active=True)
    first_name = (order.buyer_name or "").split(" ")[0] or "kak"
    ctx = {
        "nama": first_name,
        "kode": order.code,
        "event": order.event.name,
        "tahap": order.phase.name,
        "nominal": format_rupiah(order.fee_due),
        "batas_waktu": format_local(order.fee_deadline),
        "rekening": "\n".join(f"{a.bank_name} {a.account_number} a.n. {a.account_holder}" for a in accounts),
        "link_lacak": tracking_url(order),
        "ringkasan_tiket": _ticket_summary(order),
        "ringkasan_hasil": _result_summary(order),
        "brand": site.brand_name,
        "alasan": "",
        "va_bank": "",
        "va_nomor": "",
        "va_batas": "",
        "detail_penyerahan": "",
    }
    for key, value in (extra or {}).items():
        if key == "nominal" and isinstance(value, int):
            value = format_rupiah(value)
        elif key in ("batas_waktu", "va_batas") and hasattr(value, "tzinfo"):
            value = format_local(value)
        ctx[key] = value
    return ctx


def _template(key: str):
    """(body, send_email) dari DB; cadangan default; None bila dinonaktifkan."""
    tpl = MessageTemplate.objects.filter(key=key).first()
    if tpl is not None:
        return (tpl.body, tpl.send_email) if tpl.is_active else None
    if key in DEFAULT_TEMPLATES:
        _, body, send_email = DEFAULT_TEMPLATES[key]
        return body, send_email
    return None


def _create(order, key, channel, recipient, text, dedupe_key):
    try:
        with transaction.atomic():
            return Notification.objects.create(
                order=order, template_key=key, channel=channel, recipient=recipient,
                rendered_text=text, dedupe_key=dedupe_key[:191],
            )
    except IntegrityError:
        return None  # sudah pernah dibuat (dedupe)


def enqueue(order, key: str, *, extra: dict | None = None, dedupe: str | None = None) -> list:
    """Siapkan kabar untuk pesanan. Mengembalikan daftar Notification baru."""
    template = _template(key)
    if template is None:
        return []
    body, send_email = template
    base = dedupe or f"{order.code}:{key}"
    if Notification.objects.filter(dedupe_key__startswith=base + ":").exists():
        return []
    text = render(body, build_context(order, extra))
    created = []
    if key not in EMAIL_ONLY_KEYS and order.buyer_whatsapp:
        created.append(_create(order, key, NotificationChannel.WA, order.buyer_whatsapp, text, f"{base}:WA"))
    if (send_email and key not in WA_ONLY_KEYS and order.buyer_email
            and SiteSetting.load().email_notifications_enabled):
        created.append(_create(order, key, NotificationChannel.EMAIL, order.buyer_email, text, f"{base}:EMAIL"))
    return [n for n in created if n is not None]


def discard_pending(order, keys) -> int:
    """Hapus kabar yang BELUM dikirim (mis. hasil war yang dikoreksi/undo)."""
    deleted, _ = Notification.objects.filter(
        order=order, template_key__in=list(keys), status=NotificationStatus.PERLU_DIKIRIM
    ).delete()
    return deleted
