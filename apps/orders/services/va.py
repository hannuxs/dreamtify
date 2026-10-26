"""
Info VA saat war (docs/02 §8). Status VaNotice berubah di sini; status pesanan
tidak berubah (hasil tiket tetap diisi lewat `transitions.set_slot_result`).

- ADMIN   : tim mengirim VA untuk pesanan metode VA → customer bayar sendiri.
- CUSTOMER: customer titip bayar yang war mandiri & lebih dulu secured mengirim
            VA-nya agar dibayarkan tim (bisa dimatikan per event).
"""
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.core import audit
from apps.core.actors import Actor
from apps.core.dates import format_local
from apps.core.enums import OrderStatus, PhaseStatus, TicketPaymentMethod, VaSource, VaStatus
from apps.core.money import format_rupiah
from apps.notifications import services as notify

from ..models import Order, OrderTimeline, TicketSlot, VaNotice
from .transitions import InvalidTransition


def _timeline(order, title, message, *, actor, is_public=True):
    OrderTimeline.objects.create(order=order, title=title, message=message, is_public=is_public,
                                 created_by_label=actor.public_label if is_public else actor.label)


@transaction.atomic
def create_va_notice(order, *, bank: str, va_number: str, amount: int, actor: Actor, expires_at=None,
                     slot_ids=(), source: str = VaSource.ADMIN, screenshot=None, note: str = "") -> VaNotice:
    order = Order.objects.select_for_update().select_related("event", "phase").get(pk=order.pk)
    if source == VaSource.CUSTOMER:
        # ASUMSI: VA mandiri hanya untuk titip bayar (uang customer ada di tim) dan hanya saat war
        if not order.event.customer_va_enabled:
            raise InvalidTransition("Pengiriman VA mandiri tidak diaktifkan untuk event ini.")
        if order.ticket_payment_method != TicketPaymentMethod.TITIP_BAYAR:
            raise InvalidTransition("VA mandiri hanya untuk pesanan titip bayar.")
        if order.phase.status != PhaseStatus.WAR:
            raise InvalidTransition("VA mandiri hanya bisa dikirim saat war berlangsung.")
    if order.status != OrderStatus.PROSES_WAR:
        raise InvalidTransition("VA hanya bisa dikirim untuk pesanan yang sedang war.")

    errors = {}
    if not (bank or "").strip():
        errors["bank"] = ["Bank wajib diisi."]
    digits = "".join(ch for ch in (va_number or "") if ch.isdigit())
    if len(digits) < 6:
        errors["va_number"] = ["Nomor VA minimal 6 digit."]
    if not amount or int(amount) <= 0:
        errors["amount"] = ["Nominal wajib diisi."]
    if expires_at and expires_at <= timezone.now():
        errors["expires_at"] = ["Batas bayar harus di masa depan."]
    if errors:
        raise ValidationError(errors)

    va = VaNotice.objects.create(order=order, source=source, bank=bank.strip()[:50], va_number=digits,
                                 amount=int(amount), expires_at=expires_at, screenshot=screenshot or "",
                                 note=(note or "").strip(), created_by=actor.user)
    slots = list(TicketSlot.objects.filter(line__order=order, pk__in=list(slot_ids)))
    if slots:
        va.slots.set(slots)
    if source == VaSource.ADMIN:
        _timeline(order, "VA untuk tiketmu sudah keluar ⏰",
                  f"{va.bank} {va.va_number} · {format_rupiah(va.amount)}"
                  + (f" · bayar sebelum {format_local(expires_at)}" if expires_at else ""), actor=actor)
        notify.enqueue(order, "VA_DIKIRIM", dedupe=f"{order.code}:VA_DIKIRIM:{va.pk}", extra={
            "va_bank": va.bank, "va_nomor": va.va_number, "nominal": va.amount, "va_batas": expires_at or ""})
    else:
        _timeline(order, "VA hasil war mandiri dikirim", f"{va.bank} · {format_rupiah(va.amount)} — tim segera membayarkan.",
                  actor=actor)
    audit.log("va.create", actor=actor, obj=order, summary=f"{order.code}: VA {va.bank} {format_rupiah(va.amount)} ({source})",
              data={"va": va.pk, "source": source, "slots": [s.pk for s in slots]})
    return va


@transaction.atomic
def claim_va_paid(va, *, actor: Actor) -> VaNotice:
    """Customer menekan "Sudah saya bayar"."""
    va = VaNotice.objects.select_for_update().select_related("order").get(pk=va.pk)
    if va.source != VaSource.ADMIN or va.status != VaStatus.AKTIF:
        raise InvalidTransition("VA ini tidak sedang menunggu pembayaran.")
    va.status = VaStatus.DIKLAIM_CUSTOMER
    va.customer_claimed_at = timezone.now()
    va.save(update_fields=["status", "customer_claimed_at", "updated_at"])
    _timeline(va.order, "Kamu konfirmasi sudah bayar VA", f"{va.bank} {va.va_number}", actor=actor)
    audit.log("va.claim", actor=actor, obj=va.order, summary=f"{va.order.code}: customer konfirmasi bayar VA {va.bank}")
    return va


@transaction.atomic
def mark_va_paid(va, *, actor: Actor) -> VaNotice:
    """Admin: VA lunas (VA customer dibayar tim, atau VA admin terkonfirmasi)."""
    va = VaNotice.objects.select_for_update().select_related("order").get(pk=va.pk)
    if va.status not in (VaStatus.AKTIF, VaStatus.DIKLAIM_CUSTOMER):
        raise InvalidTransition("VA ini sudah selesai.")
    va.status = VaStatus.LUNAS
    va.save(update_fields=["status", "updated_at"])
    title = "VA dibayar tim" if va.source == VaSource.CUSTOMER else "Pembayaran VA terkonfirmasi"
    _timeline(va.order, title, f"{va.bank} · {format_rupiah(va.amount)}", actor=actor)
    audit.log("va.paid", actor=actor, obj=va.order, summary=f"{va.order.code}: VA {va.bank} lunas")
    return va


def expire_vas(now=None) -> int:
    """Tugas berkala: VA AKTIF lewat batas → KEDALUWARSA (idempoten)."""
    now = now or timezone.now()
    return VaNotice.objects.filter(status=VaStatus.AKTIF, expires_at__lt=now).update(
        status=VaStatus.KEDALUWARSA, updated_at=now)
