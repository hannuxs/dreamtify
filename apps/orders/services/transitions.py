"""
Mesin status pesanan — docs/02 §5. SATU-SATUNYA tempat status berubah.

Setiap aksi berjalan di `transaction.atomic`, mengunci baris pesanan
(`select_for_update`), memvalidasi transisi, lalu menulis OrderTimeline,
AuditLog, dan Notification (lewat `notifications.services.enqueue`).
Transisi yang tidak sah → `InvalidTransition`.

Urutan kunci selalu: SalePhase → Order → TicketSlot (hindari deadlock).
"""
import hashlib
from dataclasses import dataclass
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.core import audit
from apps.core.actors import Actor
from apps.core.enums import (
    FULFILLMENT_DONE,
    FULFILLMENT_FLOW,
    INCOMING_PAYMENT_KINDS,
    PRE_WAR_STATUSES,
    CancelReason,
    FulfillmentStatus,
    OrderStatus,
    PaymentKind,
    PaymentStatus,
    PhaseStatus,
    SlotResult,
    SubmittedVia,
    TicketPaymentMethod,
)
from apps.core.money import format_rupiah
from apps.notifications import services as notify
from apps.notifications.defaults import RESULT_KEYS

from ..models import Order, OrderLine, OrderTimeline, Payment, TicketSlot
from . import codes, quota, settlement
from .pricing import LineInput, PricingContext, quote_order
from .validation import BuyerData, validate_order

S = OrderStatus

# Jarak minimal batas bayar fee sebelum war (docs/02 §7)
FEE_DEADLINE_BEFORE_WAR = timedelta(hours=2)
# ASUMSI D3(b): bukti ditolak → batas bayar fee diperpanjang minimal segini
REJECT_GRACE = timedelta(hours=6)

PAYMENT_STAGE = (S.MENUNGGU_FEE, S.VERIFIKASI_FEE, S.MENUNGGU_PELUNASAN, S.VERIFIKASI_PELUNASAN)

ALLOWED = {
    S.WAITING_LIST: {S.MENUNGGU_FEE, S.DIBATALKAN},
    S.MENUNGGU_FEE: {S.VERIFIKASI_FEE, S.MENUNGGU_PELUNASAN, S.VERIFIKASI_PELUNASAN, S.SIAP_WAR,
                     S.DIBATALKAN, S.HANGUS},
    S.VERIFIKASI_FEE: {S.MENUNGGU_FEE, S.MENUNGGU_PELUNASAN, S.VERIFIKASI_PELUNASAN, S.SIAP_WAR,
                       S.DIBATALKAN, S.HANGUS},
    # ASUMSI: "Hitung ulang tagihan" (admin) bisa menaikkan tagihan → kembali menunggu bayar
    S.MENUNGGU_PELUNASAN: {S.VERIFIKASI_PELUNASAN, S.SIAP_WAR, S.MENUNGGU_FEE, S.VERIFIKASI_FEE,
                           S.DIBATALKAN, S.HANGUS},
    S.VERIFIKASI_PELUNASAN: {S.MENUNGGU_PELUNASAN, S.SIAP_WAR, S.MENUNGGU_FEE, S.VERIFIKASI_FEE,
                             S.DIBATALKAN, S.HANGUS},
    S.SIAP_WAR: {S.PROSES_WAR, S.MENUNGGU_FEE, S.VERIFIKASI_FEE, S.MENUNGGU_PELUNASAN,
                 S.VERIFIKASI_PELUNASAN, S.DIBATALKAN, S.HANGUS},
    S.PROSES_WAR: {S.PENYELESAIAN, S.SELESAI, S.DIBATALKAN},
    # ASUMSI D4: koreksi/undo hasil selama tahap masih WAR → kembali PROSES_WAR
    S.PENYELESAIAN: {S.SELESAI, S.PROSES_WAR, S.DIBATALKAN},
    S.SELESAI: {S.PROSES_WAR},
    S.HANGUS: {S.DIBATALKAN},  # admin batalkan / event batal → refund penuh
    S.DIBATALKAN: set(),
}


class InvalidTransition(Exception):
    """Aksi tidak boleh dilakukan pada status/keadaan saat ini."""


class QuotaFull(InvalidTransition):
    pass


class SlotConflict(Exception):
    """Tiket sudah diubah admin lain (versi berbeda)."""

    def __init__(self, slot):
        super().__init__("Tiket ini baru saja diubah admin lain. Muat ulang lalu coba lagi.")
        self.slot = slot


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _now(now=None):
    return now or timezone.now()


def _lock(order) -> Order:
    pk = order.pk if isinstance(order, Order) else order
    return Order.objects.select_for_update().select_related("event", "phase").get(pk=pk)


def _timeline(order, title, message="", *, actor: Actor, status="", is_public=True):
    OrderTimeline.objects.create(
        order=order, status=status, title=title, message=message,
        is_public=is_public, created_by_label=actor.public_label if is_public else actor.label,
    )


def _change_status(order, to, *, actor: Actor, title: str, message: str = "",
                   cancel_reason=None, data: dict | None = None):
    frm = order.status
    if to not in ALLOWED.get(frm, set()):
        raise InvalidTransition(
            f"Status {S(frm).label} tidak bisa diubah menjadi {S(to).label}.")
    order.status = to
    fields = ["status", "updated_at"]
    if cancel_reason:
        order.cancel_reason = cancel_reason
        fields.append("cancel_reason")
    order.save(update_fields=fields)
    _timeline(order, title, message, actor=actor, status=to)
    audit.log("order.status", actor=actor, obj=order,
              summary=f"{order.code}: {frm} → {to}",
              data={"from": frm, "to": to, "reason": cancel_reason or "", **(data or {})})


def fee_deadline_for(phase, start, window_hours: int):
    """min(mulai + jendela bayar, war − 2 jam) — docs/02 §7."""
    deadline = start + timedelta(hours=window_hours)
    if phase.war_at:
        deadline = min(deadline, phase.war_at - FEE_DEADLINE_BEFORE_WAR)
    return deadline


def _assign_unique_code(order):
    """Kode unik nominal (bila event mengaktifkannya) saat masuk MENUNGGU_FEE."""
    if not order.event.unique_code_enabled:
        return
    code = codes.pick_unique_code(order.event, exclude_order_id=order.pk)
    if code is None:
        return
    quote_before = order.fee_due + order.unique_discount
    order.unique_code = code
    order.unique_discount = code
    order.fee_due = max(0, quote_before - code)
    order.save(update_fields=["unique_code", "unique_discount", "fee_due", "updated_at"])


def _fresh_order(order) -> Order:
    """Instance baru (tanpa cache prefetch) agar perhitungan memakai data terkini."""
    return Order.objects.select_related("event", "phase").get(pk=order.pk)


# ---------------------------------------------------------------------------
# Pembuatan pesanan
# ---------------------------------------------------------------------------

def create_order(*, phase, buyer: BuyerData, lines: list, payment_method: str, actor: Actor,
                 now=None, enforce_schedule: bool = True, source_ip=None, user_agent: str = "") -> Order:
    """Buat pesanan baru → MENUNGGU_FEE (kuota cukup) atau WAITING_LIST."""
    now = _now(now)
    for attempt in range(3):
        try:
            return _create_order(phase=phase, buyer=buyer, lines=lines, payment_method=payment_method,
                                 actor=actor, now=now, enforce_schedule=enforce_schedule,
                                 source_ip=source_ip, user_agent=user_agent)
        except IntegrityError:
            if attempt == 2:
                raise  # kode bentrok 3x berturut-turut: hampir mustahil


@transaction.atomic
def _create_order(*, phase, buyer, lines, payment_method, actor, now, enforce_schedule, source_ip, user_agent):
    from apps.core.crypto import nik_hash

    phase = quota.lock_phase(phase.pk)
    event = phase.event
    ctx = PricingContext.for_phase(phase)
    active_ids = {cid for cid, c in ctx.categories.items() if c.is_active}
    buyer, lines = validate_order(event=event, phase=phase, buyer=buyer, lines=lines,
                                  payment_method=payment_method, active_category_ids=active_ids,
                                  now=now, enforce_schedule=enforce_schedule)
    try:
        quote = quote_order(ctx, [LineInput(ln.service_type, ln.quantity, ln.category_ids) for ln in lines],
                            payment_method)
    except ValueError as exc:  # PricingError
        raise ValidationError({"lines": [str(exc)]}) from exc

    fits = quota.can_fit(phase, quote.total_tickets)
    status = S.MENUNGGU_FEE if fits else S.WAITING_LIST
    deadline = None
    if fits:
        deadline = fee_deadline_for(phase, now, event.fee_payment_window_hours)
        if enforce_schedule and deadline <= now:
            # ASUMSI D3(a): terlalu dekat dengan war untuk sempat bayar fee
            raise ValidationError({"phase": ["Pemesanan tahap ini sudah ditutup (kurang dari 2 jam sebelum war)."]})

    order = Order.objects.create(
        code=codes.new_order_code(),
        event=event,
        phase=phase,
        status=status,
        ticket_payment_method=payment_method,
        buyer_name=buyer.name,
        buyer_whatsapp=buyer.whatsapp,
        buyer_email=buyer.email,
        buyer_instagram=buyer.instagram,
        referral=buyer.referral,
        customer_note=buyer.note,
        fee_due=quote.initial_due,
        pelunasan_due=quote.pelunasan_due,
        pricing_snapshot=ctx.to_snapshot(),
        fee_deadline=deadline,
        agreed_terms_at=now,
        source_ip=source_ip,
        user_agent=(user_agent or "")[:255],
    )

    hashes = []
    for i, (data, q) in enumerate(zip(lines, quote.lines)):
        h = data.holder
        digest = nik_hash(h.nik) if h.nik else ""
        if digest:
            hashes.append(digest)
        line = OrderLine.objects.create(
            order=order, sort_order=i, service_type=data.service_type, quantity=data.quantity,
            cat_primary_id=data.primary, cat_backup1_id=data.backup1, cat_backup2_id=data.backup2,
            holder_name=h.name, holder_nik=h.nik, holder_nik_hash=digest, holder_nik_last4=h.nik[-4:],
            holder_gender=h.gender, holder_birth_date=h.birth_date, holder_email=h.email,
            holder_whatsapp=h.whatsapp, holder_instagram=h.instagram,
            holder_membership_no=h.membership_no, same_as_buyer=h.same_as_buyer,
            tier_snapshot=q.tier, fee_per_ticket_snapshot=q.fee_per_ticket,
            price_basis_per_ticket_snapshot=q.price_basis_per_ticket,
            early_booking_per_ticket_snapshot=q.early_booking_per_ticket,
        )
        TicketSlot.objects.bulk_create([TicketSlot(line=line, index=n) for n in range(1, data.quantity + 1)])

    _flag_duplicate_nik(order, hashes)
    if status == S.MENUNGGU_FEE:
        _assign_unique_code(order)

    if status == S.MENUNGGU_FEE:
        _timeline(order, "Pesanan dibuat",
                  f"Silakan bayar fee {format_rupiah(order.fee_due)} sebelum batas waktu.",
                  actor=actor, status=status)
        notify.enqueue(order, "PESANAN_DIBUAT")
    else:
        _timeline(order, "Masuk waiting list",
                  "Kuota sedang penuh. Kamu belum perlu bayar; kami kabari bila ada slot.",
                  actor=actor, status=status)
        notify.enqueue(order, "WAITING_LIST_MASUK")
    audit.log("order.create", actor=actor, obj=order,
              summary=f"{order.code} dibuat ({status}), {quote.total_tickets} tiket",
              data={"status": status, "tickets": quote.total_tickets, "fee_due": order.fee_due,
                    "pelunasan_due": order.pelunasan_due})
    return order


def _flag_duplicate_nik(order, hashes):
    """docs/02 §3.5: NIK sama lebih dari sekali di satu tahap → peringatan admin (tidak memblokir)."""
    if not hashes:
        return
    dup_within = len(hashes) != len(set(hashes))
    others = (OrderLine.objects.filter(order__phase_id=order.phase_id, holder_nik_hash__in=set(hashes))
              .exclude(order=order)
              .exclude(order__status__in=(S.DIBATALKAN, S.HANGUS))
              .values_list("order_id", flat=True))
    other_ids = set(others)
    if dup_within or other_ids:
        order.has_duplicate_nik_warning = True
        order.save(update_fields=["has_duplicate_nik_warning", "updated_at"])
        Order.objects.filter(pk__in=other_ids).update(has_duplicate_nik_warning=True)


# ---------------------------------------------------------------------------
# Pembayaran
# ---------------------------------------------------------------------------

def _kind_for_status(order) -> str:
    if order.status in (S.MENUNGGU_FEE, S.VERIFIKASI_FEE):
        return PaymentKind.FEE
    if order.status in (S.MENUNGGU_PELUNASAN, S.VERIFIKASI_PELUNASAN):
        return PaymentKind.PELUNASAN
    if order.status in (S.PROSES_WAR, S.PENYELESAIAN) and settlement.balance(order) < 0:
        return PaymentKind.KEKURANGAN
    raise InvalidTransition("Pesanan ini sedang tidak menunggu pembayaran.")


@transaction.atomic
def submit_payment(order, *, amount: int, actor: Actor, kind: str | None = None, sender_name: str = "",
                   sender_bank: str = "", transfer_date=None, proof=None, destination_account=None) -> Payment:
    """Customer/admin mengirim bukti transfer → status VERIFIKASI_*."""
    order = _lock(order)
    expected = _kind_for_status(order)
    kind = kind or expected
    if kind != expected:
        raise InvalidTransition("Jenis pembayaran tidak sesuai dengan status pesanan.")
    if int(amount) <= 0:
        raise ValidationError({"amount": ["Nominal transfer harus lebih dari 0."]})
    if not proof and not actor.is_staff:
        raise ValidationError({"proof": ["Bukti transfer wajib diupload."]})

    payment = Payment.objects.create(
        order=order, kind=kind, amount_claimed=int(amount), sender_name=sender_name,
        sender_bank=sender_bank, transfer_date=transfer_date, proof=proof or "",
        destination_account=destination_account,
        submitted_via=SubmittedVia.ADMIN if actor.is_staff else SubmittedVia.CUSTOMER,
    )
    title = "Bukti transfer dikirim"
    message = f"{payment.get_kind_display()} {format_rupiah(payment.amount_claimed)} sedang kami cek."
    if order.status == S.MENUNGGU_FEE:
        _change_status(order, S.VERIFIKASI_FEE, actor=actor, title=title, message=message)
    elif order.status == S.MENUNGGU_PELUNASAN:
        _change_status(order, S.VERIFIKASI_PELUNASAN, actor=actor, title=title, message=message)
    else:
        _timeline(order, title, message, actor=actor)
    audit.log("payment.submit", actor=actor, obj=payment,
              summary=f"{order.code}: bukti {kind} {payment.amount_claimed}",
              data={"order": order.code, "kind": kind, "amount": payment.amount_claimed})
    return payment


def _lock_payment(payment) -> tuple[Order, Payment]:
    order = _lock(payment.order_id)
    payment = Payment.objects.select_for_update().get(pk=payment.pk)
    if payment.status != PaymentStatus.MENUNGGU:
        raise InvalidTransition("Pembayaran ini sudah diproses.")
    if payment.kind not in INCOMING_PAYMENT_KINDS:
        raise InvalidTransition("Jenis pembayaran ini tidak diverifikasi.")
    return order, payment


@transaction.atomic
def verify_payment(payment, *, actor: Actor, amount_received: int | None = None, now=None) -> Payment:
    order, payment = _lock_payment(payment)
    received = payment.amount_claimed if amount_received is None else int(amount_received)
    if received < 0:
        raise ValidationError({"amount_received": ["Nominal tidak valid."]})
    payment.status = PaymentStatus.DITERIMA
    payment.amount_received = received
    payment.verified_by = actor.user
    payment.verified_at = _now(now)
    payment.save(update_fields=["status", "amount_received", "verified_by", "verified_at", "updated_at"])
    _timeline(order, "Pembayaran diterima",
              f"{payment.get_kind_display()} {format_rupiah(received)} sudah kami terima.", actor=actor)
    audit.log("payment.verify", actor=actor, obj=payment,
              summary=f"{order.code}: {payment.kind} diterima {received} (klaim {payment.amount_claimed})",
              data={"order": order.code, "claimed": payment.amount_claimed, "received": received})
    _after_payment_change(order, actor=actor, now=now)
    return payment


@transaction.atomic
def reject_payment(payment, *, reason: str, actor: Actor, now=None) -> Payment:
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError({"reason": ["Alasan penolakan wajib diisi."]})
    order, payment = _lock_payment(payment)
    payment.status = PaymentStatus.DITOLAK
    payment.reject_reason = reason
    payment.verified_by = actor.user
    payment.verified_at = _now(now)
    payment.save(update_fields=["status", "reject_reason", "verified_by", "verified_at", "updated_at"])
    _timeline(order, "Bukti transfer belum bisa diterima", reason, actor=actor)
    audit.log("payment.reject", actor=actor, obj=payment, summary=f"{order.code}: {payment.kind} ditolak",
              data={"order": order.code, "reason": reason})
    _after_payment_change(order, actor=actor, now=now)
    order.refresh_from_db()
    notify.enqueue(order, "BUKTI_DITOLAK", extra={"alasan": reason}, dedupe=f"{order.code}:BUKTI_DITOLAK:{payment.pk}")
    return payment


def _after_payment_change(order, *, actor: Actor, now=None):
    """Hitung ulang posisi pesanan setelah pembayaran diterima/ditolak (docs/02 §4.2)."""
    now = _now(now)
    fresh = _fresh_order(order)
    summary = settlement.summarize(fresh)
    pending = bool(settlement.pending_incoming(fresh))

    if order.status in PAYMENT_STAGE + (S.SIAP_WAR,):
        titip = order.ticket_payment_method == TicketPaymentMethod.TITIP_BAYAR
        if summary.paid_in >= summary.total_before_war:
            target = S.SIAP_WAR
        elif titip and summary.paid_in >= summary.initial_due:
            target = S.VERIFIKASI_PELUNASAN if pending else S.MENUNGGU_PELUNASAN
        else:
            target = S.VERIFIKASI_FEE if pending else S.MENUNGGU_FEE
        if target == order.status:
            return
        was_fee_stage = order.status in (S.MENUNGGU_FEE, S.VERIFIKASI_FEE)
        messages = {
            S.SIAP_WAR: ("Siap war 🎫", "Pembayaran lengkap. Tinggal tunggu hari war!"),
            S.MENUNGGU_PELUNASAN: ("Menunggu pelunasan",
                                   f"Fee diterima. Sisa pelunasan {format_rupiah(summary.remaining_before_war)}."),
            S.VERIFIKASI_PELUNASAN: ("Bukti pelunasan sedang dicek", ""),
            S.MENUNGGU_FEE: ("Menunggu pembayaran fee",
                             f"Fee masih kurang {format_rupiah(summary.remaining_initial)}."),
            S.VERIFIKASI_FEE: ("Bukti fee sedang dicek", ""),
        }
        title, message = messages[target]
        _change_status(order, target, actor=actor, title=title, message=message)

        if target == S.MENUNGGU_FEE:
            # ASUMSI D3(b): beri waktu upload ulang setelah bukti ditolak
            grace = now + REJECT_GRACE
            if order.phase.war_at:
                grace = min(grace, order.phase.war_at - FEE_DEADLINE_BEFORE_WAR)
            if order.fee_deadline is None or order.fee_deadline < grace:
                order.fee_deadline = grace
                order.save(update_fields=["fee_deadline", "updated_at"])
        if target == S.SIAP_WAR:
            notify.enqueue(order, "SIAP_WAR", extra={"batas_waktu": order.phase.war_at})
        elif target in (S.MENUNGGU_PELUNASAN, S.VERIFIKASI_PELUNASAN) and was_fee_stage:
            notify.enqueue(order, "FEE_DITERIMA", extra={"nominal": summary.initial_due})
            if target == S.MENUNGGU_PELUNASAN:
                notify.enqueue(order, "TAGIHAN_PELUNASAN", extra={
                    "nominal": summary.remaining_before_war, "batas_waktu": order.phase.pelunasan_deadline})
    elif order.status in (S.PROSES_WAR, S.PENYELESAIAN):
        _refresh_completion(order, actor=actor)


# ---------------------------------------------------------------------------
# Waiting list & pembatalan
# ---------------------------------------------------------------------------

@transaction.atomic
def promote_from_waitlist(order, *, actor: Actor, now=None) -> Order:
    now = _now(now)
    phase = quota.lock_phase(order.phase_id)
    order = _lock(order)
    if order.status != S.WAITING_LIST:
        raise InvalidTransition("Pesanan ini tidak sedang di waiting list.")
    tickets = sum(line.quantity for line in order.lines.all())
    if not quota.can_fit(phase, tickets):
        raise QuotaFull(f"Kuota tidak cukup untuk {tickets} tiket.")
    deadline = fee_deadline_for(phase, now, order.event.fee_payment_window_hours)
    if deadline <= now:
        raise InvalidTransition("Sudah terlalu dekat dengan waktu war untuk menaikkan pesanan.")
    order.fee_deadline = deadline
    order.save(update_fields=["fee_deadline", "updated_at"])
    _change_status(order, S.MENUNGGU_FEE, actor=actor, title="Dapat slot dari waiting list 🎉",
                   message=f"Silakan bayar fee {format_rupiah(order.fee_due)} sebelum batas waktu.")
    _assign_unique_code(order)
    notify.enqueue(order, "WAITING_LIST_NAIK", extra={"batas_waktu": order.fee_deadline})
    return order


def _cancel(order, status, reason, *, actor: Actor, note: str = ""):
    label = CancelReason(reason).label
    preview = settlement.cancellation_preview(_fresh_order(order), reason)
    message = note or label
    if preview.refund:
        message += f". Dana yang kembali: {format_rupiah(preview.refund)}."
    _change_status(order, status, actor=actor, title=S(status).label, message=message,
                   cancel_reason=reason, data={"refund": preview.refund, "forfeited": preview.final_due})
    order.is_late_pelunasan = False
    order.save(update_fields=["is_late_pelunasan", "updated_at"])
    notify.enqueue(order, "DIBATALKAN", extra={"alasan": label.lower()})
    return preview


@transaction.atomic
def cancel_by_customer(order, *, actor: Actor):
    """Customer batal sebelum war: DIBATALKAN (belum ada uang) / HANGUS (fee hangus)."""
    order = _lock(order)
    if order.status not in PRE_WAR_STATUSES:
        raise InvalidTransition("Pesanan tidak bisa dibatalkan sendiri sejak war dimulai.")
    status = settlement.cancel_status_for(_fresh_order(order), CancelReason.BATAL_CUSTOMER)
    return _cancel(order, status, CancelReason.BATAL_CUSTOMER, actor=actor)


@transaction.atomic
def cancel_by_admin(order, *, actor: Actor, reason: str = CancelReason.BATAL_ADMIN, note: str = ""):
    """Admin (Owner) membatalkan / konser batal → DIBATALKAN, refund penuh."""
    if reason not in (CancelReason.BATAL_ADMIN, CancelReason.EVENT_BATAL):
        raise InvalidTransition("Alasan pembatalan admin tidak valid.")
    order = _lock(order)
    if order.status in (S.SELESAI, S.DIBATALKAN):
        raise InvalidTransition("Pesanan ini tidak bisa dibatalkan.")
    return _cancel(order, S.DIBATALKAN, reason, actor=actor, note=note)


@transaction.atomic
def release_slot(order, *, actor: Actor, now=None):
    """"Lepas slot" untuk pesanan yang lewat batas pelunasan (kebijakan event)."""
    now = _now(now)
    order = _lock(order)
    if order.status != S.MENUNGGU_PELUNASAN:
        raise InvalidTransition("Hanya pesanan yang menunggu pelunasan yang bisa dilepas.")
    deadline = order.phase.pelunasan_deadline
    if deadline is None or now < deadline:
        raise InvalidTransition("Batas pelunasan belum lewat.")
    status = settlement.cancel_status_for(order, CancelReason.LEWAT_BATAS_PELUNASAN)
    return _cancel(order, status, CancelReason.LEWAT_BATAS_PELUNASAN, actor=actor)


@transaction.atomic
def cancel_expired_fee(order, *, actor: Actor | None = None, now=None) -> bool:
    """Tugas berkala: MENUNGGU_FEE lewat batas → DIBATALKAN. Idempoten.

    ASUMSI D3(c): hanya bila belum ada pembayaran diterima maupun sedang dicek.
    """
    now = _now(now)
    actor = actor or Actor.system()
    order = _lock(order)
    if order.status != S.MENUNGGU_FEE or not order.fee_deadline or order.fee_deadline > now:
        return False
    if settlement.has_money(_fresh_order(order)):
        return False
    _cancel(order, S.DIBATALKAN, CancelReason.LEWAT_BATAS_FEE, actor=actor)
    return True


# ---------------------------------------------------------------------------
# War
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class WarStart:
    started: list  # kode pesanan yang masuk PROSES_WAR
    not_ready: list  # kode pesanan yang belum siap (tidak ikut)


@transaction.atomic
def start_war(phase, *, actor: Actor, now=None) -> WarStart:
    now = _now(now)
    phase = quota.lock_phase(phase.pk)
    if phase.status not in (PhaseStatus.BUKA, PhaseStatus.TUTUP):
        raise InvalidTransition("War hanya bisa dimulai dari tahap berstatus Buka/Tutup.")
    phase.status = PhaseStatus.WAR
    phase.war_started_at = now
    phase.save(update_fields=["status", "war_started_at", "updated_at"])
    started = []
    for order in Order.objects.select_for_update().filter(phase=phase, status=S.SIAP_WAR).order_by("created_at"):
        _change_status(order, S.PROSES_WAR, actor=actor, title="War dimulai",
                       message="Tim kami sedang berjuang untuk tiketmu. Pantau halaman ini ya!")
        started.append(order.code)
    not_ready = list(Order.objects.filter(phase=phase, status__in=PAYMENT_STAGE)
                     .order_by("created_at").values_list("code", flat=True))
    audit.log("phase.war_start", actor=actor, obj=phase, summary=f"War dimulai: {phase}",
              data={"started": len(started), "not_ready": len(not_ready)})
    return WarStart(started=started, not_ready=not_ready)


def _has_settlement_activity(order) -> bool:
    if order.payments.filter(kind__in=(PaymentKind.REFUND, PaymentKind.KEKURANGAN)).exists():
        return True
    return TicketSlot.objects.filter(line__order=order).exclude(
        fulfillment_status__in=(FulfillmentStatus.MENUNGGU, FulfillmentStatus.TIDAK_PERLU)).exists()


def _result_digest(order) -> str:
    raw = ",".join(f"{s.pk}:{s.result}:{s.secured_category_id}"
                   for line in order.lines.all() for s in line.slots.all())
    return hashlib.sha1(raw.encode()).hexdigest()[:10]


@transaction.atomic
def set_slot_result(slot, result: str, *, actor: Actor, category=None, ticket_reference: str = "",
                    expected_version: int | None = None, now=None) -> TicketSlot:
    """Isi/ubah/undo hasil war satu tiket. result=MENUNGGU berarti undo."""
    now = _now(now)
    order = _lock(slot.line.order_id)
    slot = TicketSlot.objects.select_for_update().select_related("line").get(pk=slot.pk)
    if expected_version is not None and slot.version != expected_version:
        raise SlotConflict(slot)
    if result not in SlotResult.values:
        raise InvalidTransition("Hasil tidak dikenal.")

    if order.status == S.PROSES_WAR:
        pass
    elif order.status in (S.PENYELESAIAN, S.SELESAI):
        # ASUMSI D4: koreksi hanya selama tahap masih WAR & belum ada refund/penyerahan
        if order.phase.status != PhaseStatus.WAR or _has_settlement_activity(order):
            raise InvalidTransition("Hasil sudah final dan tidak bisa diubah di Mode War.")
    else:
        raise InvalidTransition("Pesanan ini tidak sedang dalam proses war.")

    line = slot.line
    if result == SlotResult.SECURED:
        if category is None:
            raise ValidationError({"category": ["Pilih kategori yang didapat."]})
        if category.event_id != order.event_id:
            raise ValidationError({"category": ["Kategori bukan milik event ini."]})
        if category.pk not in line.category_ids and not order.event.fallback_any_category:
            raise ValidationError({"category": ["Kategori di luar pilihan tidak diizinkan untuk event ini."]})
        slot.secured_category = category
        slot.fulfillment_status = FulfillmentStatus.MENUNGGU
    else:
        slot.secured_category = None
        slot.fulfillment_status = (FulfillmentStatus.MENUNGGU if result == SlotResult.MENUNGGU
                                   else FulfillmentStatus.TIDAK_PERLU)
    previous = slot.result
    slot.result = result
    slot.ticket_reference = (ticket_reference or "").strip()[:100] if result == SlotResult.SECURED else ""
    slot.result_set_by = actor.user
    slot.result_set_at = now if result != SlotResult.MENUNGGU else None
    slot.version += 1
    slot.save()
    audit.log("slot.result", actor=actor, obj=slot,
              summary=f"{order.code} tiket {line.sort_order + 1}.{slot.index}: {previous} → {result}",
              data={"order": order.code, "from": previous, "to": result,
                    "category": category.name if category else ""})

    fresh = _fresh_order(order)
    if settlement.all_results_in(fresh):
        notify.discard_pending(order, RESULT_KEYS)
        if order.status != S.PROSES_WAR:  # koreksi setelah hasil keluar
            _change_status(order, S.PROSES_WAR, actor=actor, title="Hasil war dikoreksi",
                           message="Tim kami memperbarui hasil war tiketmu.")
        _announce_results(order, actor=actor)
        _refresh_completion(order, actor=actor)
    elif order.status in (S.PENYELESAIAN, S.SELESAI):
        notify.discard_pending(order, RESULT_KEYS)
        _change_status(order, S.PROSES_WAR, actor=actor, title="Hasil war dikoreksi",
                       message="Tim kami memperbarui hasil war tiketmu.")
    return slot


def _announce_results(order, *, actor: Actor):
    slots = list(TicketSlot.objects.filter(line__order=order))
    secured = sum(1 for s in slots if s.result == SlotResult.SECURED)
    if secured == len(slots):
        key, title = "HASIL_SECURED", "Hasil war: semua tiket dapat 🎉"
    elif secured == 0:
        key, title = "HASIL_GAGAL", "Hasil war: belum dapat tiket"
    else:
        key, title = "HASIL_SEBAGIAN", f"Hasil war: {secured} dari {len(slots)} tiket dapat"
    _timeline(order, title, "Rincian per tiket & saldo ada di halaman ini.", actor=actor)
    fresh = _fresh_order(order)
    notify.enqueue(fresh, key, dedupe=f"{order.code}:HASIL:{_result_digest(fresh)}")


@transaction.atomic
def finish_war(phase, *, actor: Actor, mark_rest_failed: bool = False, now=None):
    """Selesaikan war: tiket yang belum diisi harus diisi, atau ditandai Gagal (konfirmasi)."""
    now = _now(now)
    phase = quota.lock_phase(phase.pk)
    if phase.status != PhaseStatus.WAR:
        raise InvalidTransition("Tahap ini tidak sedang war.")
    pending = list(TicketSlot.objects.filter(line__order__phase=phase, line__order__status=S.PROSES_WAR,
                                             result=SlotResult.MENUNGGU).select_related("line"))
    if pending and not mark_rest_failed:
        raise InvalidTransition(f"Masih ada {len(pending)} tiket yang belum diisi hasilnya.")
    for slot in pending:
        set_slot_result(slot, SlotResult.GAGAL, actor=actor, now=now)
    phase.status = PhaseStatus.SELESAI
    phase.war_finished_at = now
    phase.save(update_fields=["status", "war_finished_at", "updated_at"])
    audit.log("phase.war_finish", actor=actor, obj=phase, summary=f"War selesai: {phase}",
              data={"marked_failed": len(pending)})
    return len(pending)


# ---------------------------------------------------------------------------
# Penyelesaian
# ---------------------------------------------------------------------------

@transaction.atomic
def set_fulfillment(slot, status: str, *, actor: Actor, method: str = "", detail: str = "",
                    receiver_name: str = "", note: str = "", photo=None, eticket=None, now=None) -> TicketSlot:
    """Penyerahan per tiket SECURED (docs/02 §9). Hanya maju, tidak mundur."""
    now = _now(now)
    order = _lock(slot.line.order_id)
    slot = TicketSlot.objects.select_for_update().select_related("line", "secured_category").get(pk=slot.pk)
    if slot.result != SlotResult.SECURED:
        raise InvalidTransition("Penyerahan hanya untuk tiket yang didapat.")
    if order.status not in (S.PROSES_WAR, S.PENYELESAIAN):
        raise InvalidTransition("Pesanan ini tidak sedang dalam penyelesaian.")
    flow = FULFILLMENT_FLOW[slot.line.service_type]
    if status not in flow or flow.index(status) < flow.index(slot.fulfillment_status):
        raise InvalidTransition("Status penyerahan tidak valid untuk layanan ini.")
    if status == FulfillmentStatus.SIAP_DISERAHKAN and not (method or slot.handover_method):
        raise ValidationError({"method": ["Pilih metode penyerahan."]})
    if status == FulfillmentStatus.DISERAHKAN and not (receiver_name or slot.handover_receiver_name):
        raise ValidationError({"receiver_name": ["Nama penerima wajib diisi."]})

    previous = slot.fulfillment_status
    slot.fulfillment_status = status
    if method:
        slot.handover_method = method
    if detail:
        slot.handover_detail = detail
    if receiver_name:
        slot.handover_receiver_name = receiver_name
    if note:
        slot.fulfillment_note = note
    if photo:
        slot.handover_photo = photo
    if eticket:
        slot.eticket_file = eticket
    slot.fulfillment_updated_at = now
    slot.save()

    holder = slot.line.holder_name
    detail_text = " · ".join(x for x in (slot.get_handover_method_display() if slot.handover_method else "",
                                         slot.handover_detail) if x)
    _timeline(order, f"{FulfillmentStatus(status).label} — {holder}", detail_text or slot.fulfillment_note,
              actor=actor)
    audit.log("slot.fulfillment", actor=actor, obj=slot,
              summary=f"{order.code} tiket {slot.index}: {previous} → {status}",
              data={"order": order.code, "from": previous, "to": status})
    if status == FulfillmentStatus.SIAP_DISERAHKAN:
        notify.enqueue(order, "GELANG_SIAP", extra={"detail_penyerahan": detail_text},
                       dedupe=f"{order.code}:GELANG_SIAP:{slot.pk}")
    elif status == FulfillmentStatus.INFO_DIKIRIM:
        info = slot.fulfillment_note or order.event.redemption_info
        notify.enqueue(order, "ETIKET_INFO", extra={"detail_penyerahan": info},
                       dedupe=f"{order.code}:ETIKET_INFO:{slot.pk}")
    _refresh_completion(order, actor=actor)
    return slot


@transaction.atomic
def record_refund(order, *, amount: int, actor: Actor, proof=None, transfer_date=None, note: str = "",
                  now=None) -> Payment:
    """Catat refund yang sudah ditransfer admin (boleh bertahap)."""
    order = _lock(order)
    amount = int(amount)
    available = settlement.balance(_fresh_order(order))
    if amount <= 0:
        raise ValidationError({"amount": ["Nominal refund harus lebih dari 0."]})
    if amount > available:
        raise ValidationError({"amount": [f"Melebihi saldo refund ({format_rupiah(max(0, available))})."]})
    payment = Payment.objects.create(
        order=order, kind=PaymentKind.REFUND, status=PaymentStatus.DITERIMA,
        amount_claimed=amount, amount_received=amount, transfer_date=transfer_date,
        proof=proof or "", verified_by=actor.user, verified_at=_now(now),
        submitted_via=SubmittedVia.ADMIN, reject_reason="",
    )
    _timeline(order, "Refund ditransfer", f"Refund {format_rupiah(amount)} sudah kami transfer. {note}".strip(),
              actor=actor)
    audit.log("payment.refund", actor=actor, obj=payment, summary=f"{order.code}: refund {amount}",
              data={"order": order.code, "amount": amount})
    notify.enqueue(order, "REFUND_SELESAI", extra={"nominal": amount}, dedupe=f"{order.code}:REFUND_SELESAI:{payment.pk}")
    _refresh_completion(order, actor=actor)
    return payment


@transaction.atomic
def refresh_completion(order, *, actor: Actor | None = None) -> Order:
    """Pindahkan PROSES_WAR → PENYELESAIAN / SELESAI bila syaratnya terpenuhi."""
    order = _lock(order)
    _refresh_completion(order, actor=actor or Actor.system())
    return order


def _refresh_completion(order, *, actor: Actor):
    if order.status not in (S.PROSES_WAR, S.PENYELESAIAN):
        return
    fresh = Order.objects.select_related("event", "phase").prefetch_related(
        "payments", "lines__slots").get(pk=order.pk)
    if not settlement.all_results_in(fresh):
        return
    summary = settlement.summarize(fresh)
    handed_over = all(
        slot.result != SlotResult.SECURED
        or slot.fulfillment_status == FULFILLMENT_DONE[line.service_type]
        for line in fresh.lines.all() for slot in line.slots.all()
    )
    if handed_over and summary.balance == 0 and not settlement.pending_incoming(fresh):
        _change_status(order, S.SELESAI, actor=actor, title="Selesai ✨",
                       message="Semua beres. Terima kasih sudah memakai Dreamtify!")
        notify.enqueue(order, "SELESAI_MINTA_TESTIMONI")
        return
    if order.status == S.PROSES_WAR:
        _change_status(order, S.PENYELESAIAN, actor=actor, title="Hasil keluar — proses penyelesaian",
                       message="Kami sedang memproses refund/kekurangan & penyerahan tiket.")
    if summary.balance > 0 and not order.refund_account_number:
        notify.enqueue(order, "REFUND_ISI_REKENING", extra={"nominal": summary.balance},
                       dedupe=f"{order.code}:REFUND_ISI_REKENING:{summary.balance}")
    elif summary.balance < 0:
        notify.enqueue(order, "KEKURANGAN_BAYAR", extra={"nominal": summary.shortfall},
                       dedupe=f"{order.code}:KEKURANGAN_BAYAR:{summary.shortfall}")


# ---------------------------------------------------------------------------
# Perubahan oleh admin: baris tiket & hitung ulang tagihan (docs/02 §11)
# ---------------------------------------------------------------------------

RECALC_STATUSES = (S.WAITING_LIST,) + PAYMENT_STAGE + (S.SIAP_WAR,)


@dataclass(frozen=True)
class RecalcPreview:
    old_initial: int
    old_pelunasan: int
    new_initial: int
    new_pelunasan: int

    @property
    def changed(self) -> bool:
        return (self.old_initial, self.old_pelunasan) != (self.new_initial, self.new_pelunasan)


def _requote(order):
    """Hitung ulang dengan harga event saat ini (unique discount tetap)."""
    ctx = PricingContext.for_phase(order.phase)
    lines = list(order.lines.all())
    quote = quote_order(ctx, [LineInput(ln.service_type, ln.quantity, tuple(ln.category_ids)) for ln in lines],
                        order.ticket_payment_method, unique_discount=order.unique_discount)
    return ctx, lines, quote


def recalculate_preview(order) -> RecalcPreview:
    _, _, quote = _requote(order)
    return RecalcPreview(order.fee_due, order.pelunasan_due, quote.initial_due, quote.pelunasan_due)


@transaction.atomic
def recalculate_order(order, *, actor: Actor, now=None) -> RecalcPreview:
    """"Hitung ulang tagihan": snapshot harga diperbarui ke harga event saat ini."""
    order = _lock(order)
    if order.status not in RECALC_STATUSES:
        raise InvalidTransition("Tagihan hanya bisa dihitung ulang sebelum war.")
    try:
        ctx, lines, quote = _requote(order)
    except ValueError as exc:  # PricingError
        raise InvalidTransition(str(exc)) from exc
    preview = RecalcPreview(order.fee_due, order.pelunasan_due, quote.initial_due, quote.pelunasan_due)
    for line, q in zip(lines, quote.lines):
        line.tier_snapshot = q.tier
        line.fee_per_ticket_snapshot = q.fee_per_ticket
        line.price_basis_per_ticket_snapshot = q.price_basis_per_ticket
        line.early_booking_per_ticket_snapshot = q.early_booking_per_ticket
        line.save(update_fields=["tier_snapshot", "fee_per_ticket_snapshot", "price_basis_per_ticket_snapshot",
                                 "early_booking_per_ticket_snapshot", "updated_at"])
    order.fee_due = quote.initial_due
    order.pelunasan_due = quote.pelunasan_due
    order.pricing_snapshot = ctx.to_snapshot()
    order.save(update_fields=["fee_due", "pelunasan_due", "pricing_snapshot", "updated_at"])
    if preview.changed:
        _timeline(order, "Tagihan diperbarui",
                  f"Tagihan awal {format_rupiah(preview.new_initial)}"
                  + (f", pelunasan {format_rupiah(preview.new_pelunasan)}" if preview.new_pelunasan else "") + ".",
                  actor=actor)
    audit.log("order.recalculate", actor=actor, obj=order, summary=f"{order.code}: tagihan dihitung ulang",
              data={"old": [preview.old_initial, preview.old_pelunasan],
                    "new": [preview.new_initial, preview.new_pelunasan]})
    if order.status != S.WAITING_LIST:
        _after_payment_change(order, actor=actor, now=now)
    return preview


@transaction.atomic
def admin_update_line(line, *, actor: Actor, quantity: int, primary: int, backup1=None, backup2=None,
                      now=None) -> OrderLine:
    """Admin mengubah jumlah/kategori satu baris sebelum war → tiket disesuaikan + hitung ulang."""
    phase = quota.lock_phase(line.order.phase_id)
    order = _lock(line.order_id)
    line = OrderLine.objects.select_for_update().get(pk=line.pk)
    if order.status not in RECALC_STATUSES:
        raise InvalidTransition("Jumlah & kategori hanya bisa diubah sebelum war.")
    event = order.event
    cats = [c for c in (primary, backup1, backup2) if c]
    errors = {}
    if not 1 <= int(quantity) <= event.max_tickets_per_holder:
        errors["quantity"] = [f"Jumlah tiket 1–{event.max_tickets_per_holder}."]
    if len(cats) != len(set(cats)):
        errors["backup1"] = ["Kategori utama, cadangan 1, dan cadangan 2 harus berbeda."]
    active = set(event.categories.filter(is_active=True).values_list("pk", flat=True))
    if any(c not in active for c in cats):
        errors["primary"] = ["Kategori tidak tersedia."]
    for n, cid in enumerate((backup1, backup2), start=1):
        if n <= event.required_backups and not cid:
            errors[f"backup{n}"] = [f"Kategori cadangan {n} wajib."]
    if errors:
        raise ValidationError(errors)
    delta = int(quantity) - line.quantity
    if delta > 0 and order.status != S.WAITING_LIST and not quota.can_fit(phase, delta):
        raise QuotaFull(f"Kuota tahap tidak cukup untuk menambah {delta} tiket.")

    before = (line.quantity, line.cat_primary_id, line.cat_backup1_id, line.cat_backup2_id)
    line.quantity = int(quantity)
    line.cat_primary_id, line.cat_backup1_id, line.cat_backup2_id = primary, backup1, backup2
    line.save()
    existing = list(line.slots.order_by("index"))
    if delta > 0:
        TicketSlot.objects.bulk_create([TicketSlot(line=line, index=len(existing) + n) for n in range(1, delta + 1)])
    elif delta < 0:
        TicketSlot.objects.filter(pk__in=[s.pk for s in existing[delta:]]).delete()
    audit.log("order.line_update", actor=actor, obj=order,
              summary=f"{order.code}: baris #{line.sort_order + 1} diubah",
              data={"line": line.pk, "before": before,
                    "after": (line.quantity, line.cat_primary_id, line.cat_backup1_id, line.cat_backup2_id)})
    recalculate_order(order, actor=actor, now=now)
    return line
