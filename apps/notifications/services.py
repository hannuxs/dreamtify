"""
Antrian kabar (docs/08).

- `enqueue(order, KEY, extra=…, dedupe=…)`: membuat Notification WA (dikirim admin dari
  Kotak Kabar lewat wa.me) dan EMAIL (dikirim otomatis bila diaktifkan). `dedupe_key`
  mencegah kabar ganda.
- Placeholder {nama}, {kode}, … dirender dari data pesanan (docs/08 §2).
"""
import re

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core.dates import format_local
from apps.core.enums import NotificationChannel, NotificationStatus, SlotResult
from apps.core.models import BankAccount, SiteSetting
from apps.core.money import format_rupiah

from .backends import EmailBackend, ManualWhatsAppBackend
from .defaults import DEFAULT_TEMPLATES, EMAIL_ONLY_KEYS, WA_ONLY_KEYS
from .models import MessageTemplate, Notification

_PLACEHOLDER = re.compile(r"\{([a-z_]+)\}")

KNOWN_PLACEHOLDERS = {
    "nama", "kode", "event", "tahap", "nominal", "batas_waktu", "rekening", "link_lacak",
    "ringkasan_tiket", "ringkasan_hasil", "va_bank", "va_nomor", "va_batas", "alasan",
    "detail_penyerahan", "brand",
}


def render(body: str, context: dict) -> str:
    """Ganti {placeholder} yang dikenal; yang tidak dikenal dibiarkan apa adanya."""
    return _PLACEHOLDER.sub(lambda m: str(context.get(m.group(1), m.group(0))), body)


def unknown_placeholders(body: str) -> list[str]:
    return sorted({p for p in _PLACEHOLDER.findall(body or "") if p not in KNOWN_PLACEHOLDERS})


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


def _accounts_text() -> str:
    return "\n".join(f"{a.bank_name} {a.account_number} a.n. {a.account_holder}"
                     for a in BankAccount.objects.filter(is_active=True))


def _apply_extra(ctx: dict, extra: dict | None) -> dict:
    for key, value in (extra or {}).items():
        if key == "nominal" and isinstance(value, int):
            value = format_rupiah(value)
        elif key in ("batas_waktu", "va_batas") and hasattr(value, "tzinfo"):
            value = format_local(value)
        ctx[key] = value
    return ctx


def build_context(order, extra: dict | None = None) -> dict:
    from apps.orders.services.links import tracking_url

    first_name = (order.buyer_name or "").split(" ")[0] or "kak"
    ctx = {
        "nama": first_name,
        "kode": order.code,
        "event": order.event.name,
        "tahap": order.phase.name,
        "nominal": format_rupiah(order.fee_due),
        "batas_waktu": format_local(order.fee_deadline),
        "rekening": _accounts_text(),
        "link_lacak": tracking_url(order),
        "ringkasan_tiket": _ticket_summary(order),
        "ringkasan_hasil": _result_summary(order),
        "brand": SiteSetting.load().brand_name,
        "alasan": "",
        "va_bank": "",
        "va_nomor": "",
        "va_batas": "",
        "detail_penyerahan": "",
    }
    return _apply_extra(ctx, extra)


def sample_context() -> dict:
    """Data contoh untuk pratinjau template di Pengaturan."""
    now = timezone.now()
    return {
        "nama": "Rina", "kode": "DRM-7KX2QP", "event": "Contoh Fanmeet", "tahap": "Presale",
        "nominal": "Rp 750.000", "batas_waktu": format_local(now), "rekening": _accounts_text() or "BCA 1234567890 a.n. Dreamtify",
        "link_lacak": "https://dreamtify.example/lacak/DRM-7KX2QP/?t=…",
        "ringkasan_tiket": "• Rina Putri · JASWAR · 2 tiket · Duality Package / CAT 1 / CAT 2",
        "ringkasan_hasil": "✅ Duality Package a.n. Rina Putri\n❌ Tidak dapat a.n. Rina Putri",
        "brand": SiteSetting.load().brand_name, "alasan": "bukti tidak terbaca",
        "va_bank": "BCA", "va_nomor": "8808123456789012", "va_batas": format_local(now),
        "detail_penyerahan": "Titik temu · Sab 10.00 di lobby GBK",
    }


def template_for(key: str):
    """(judul, isi, kirim_email) dari DB; cadangan default; None bila dinonaktifkan."""
    tpl = MessageTemplate.objects.filter(key=key).first()
    if tpl is not None:
        return (tpl.title, tpl.body, tpl.send_email) if tpl.is_active else None
    if key in DEFAULT_TEMPLATES:
        return DEFAULT_TEMPLATES[key]
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


def _deliver_email(notification_id):
    notification = Notification.objects.select_related("order").filter(pk=notification_id).first()
    if notification and notification.status == NotificationStatus.PERLU_DIKIRIM:
        EmailBackend().send(notification)


def enqueue(order, key: str, *, extra: dict | None = None, dedupe: str | None = None) -> list:
    """Siapkan kabar untuk pesanan. Mengembalikan daftar Notification baru."""
    template = template_for(key)
    if template is None:
        return []
    _, body, send_email = template
    base = dedupe or f"{order.code}:{key}"
    if Notification.objects.filter(dedupe_key__startswith=base + ":").exists():
        return []
    text = render(body, build_context(order, extra))
    created = []
    if key not in EMAIL_ONLY_KEYS and order.buyer_whatsapp:
        created.append(_create(order, key, NotificationChannel.WA, order.buyer_whatsapp, text, f"{base}:WA"))
    if (send_email and key not in WA_ONLY_KEYS and order.buyer_email
            and SiteSetting.load().email_notifications_enabled):
        email = _create(order, key, NotificationChannel.EMAIL, order.buyer_email, text, f"{base}:EMAIL")
        if email:
            created.append(email)
            transaction.on_commit(lambda pk=email.pk: _deliver_email(pk))
    return [n for n in created if n is not None]


def enqueue_manual(order, key: str, *, actor_label: str, extra: dict | None = None) -> Notification | None:
    """Kabar yang dibuat admin dari detail pesanan (boleh berulang)."""
    stamp = timezone.now().strftime("%Y%m%d%H%M%S%f")
    created = [n for n in enqueue(order, key, extra=extra, dedupe=f"{order.code}:{key}:manual:{stamp}")
               if n.channel == NotificationChannel.WA]
    return created[0] if created else None


def discard_pending(order, keys) -> int:
    """Hapus kabar yang BELUM dikirim (mis. hasil war yang dikoreksi/undo)."""
    deleted, _ = Notification.objects.filter(
        order=order, template_key__in=list(keys), status=NotificationStatus.PERLU_DIKIRIM
    ).delete()
    return deleted


# ---------------------------------------------------------------------------
# Kotak Kabar
# ---------------------------------------------------------------------------

def wa_url(notification) -> str:
    return ManualWhatsAppBackend.url(notification)


def mark_sent(notification, *, user) -> Notification:
    if notification.status != NotificationStatus.TERKIRIM:
        notification.status = NotificationStatus.TERKIRIM
        notification.sent_by = user
        notification.sent_at = timezone.now()
        notification.save(update_fields=["status", "sent_by", "sent_at", "updated_at"])
    return notification


def mark_skipped(notification, *, user) -> Notification:
    notification.status = NotificationStatus.DILEWATI
    notification.sent_by = user
    notification.sent_at = timezone.now()
    notification.save(update_fields=["status", "sent_by", "sent_at", "updated_at"])
    return notification


def update_text(notification, text: str) -> Notification:
    notification.rendered_text = (text or "").strip() or notification.rendered_text
    notification.save(update_fields=["rendered_text", "updated_at"])
    return notification


def preview(body: str) -> str:
    return render(body, sample_context())

