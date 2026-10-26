"""
Tugas berkala (tiap 15 menit; docs/02 §7). Semua langkah idempoten.

(1) batalkan MENUNGGU_FEE lewat batas, (2) pengingat fee 3 jam sebelum batas,
(3) pengingat pelunasan 24 jam sebelum batas, (4) tandai lewat batas pelunasan,
(5) VA lewat batas → KEDALUWARSA, (6) tutup tahap yang waktu pesannya lewat.
Pengingat memakai dedupe_key sehingga tidak pernah ganda.
"""
from datetime import timedelta

import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core import audit
from apps.core.actors import Actor
from apps.core.enums import OrderStatus, PhaseStatus
from apps.events.models import SalePhase
from apps.orders.models import Order
from apps.notifications import services as notify
from apps.orders.services import settlement, transitions, va

logger = logging.getLogger("dreamtify.periodic")


def cancel_expired_fees(now) -> int:
    count = 0
    for order in Order.objects.filter(status=OrderStatus.MENUNGGU_FEE, fee_deadline__lt=now).only("pk"):
        if transitions.cancel_expired_fee(order, now=now):
            count += 1
    return count


# ASUMSI: masing-masing pengingat dikirim sekali per pesanan (dedupe), bukan berulang
FEE_REMINDER_BEFORE = timedelta(hours=3)
PELUNASAN_REMINDER_BEFORE = timedelta(hours=24)


def remind_fees(now) -> int:
    count = 0
    orders = Order.objects.filter(status=OrderStatus.MENUNGGU_FEE, fee_deadline__gt=now,
                                  fee_deadline__lte=now + FEE_REMINDER_BEFORE).select_related("event", "phase")
    for order in orders:
        summary = settlement.summarize(order)
        count += bool(notify.enqueue(order, "PENGINGAT_FEE", extra={
            "nominal": summary.remaining_initial, "batas_waktu": order.fee_deadline}))
    return count


def remind_pelunasan(now) -> int:
    count = 0
    orders = Order.objects.filter(status=OrderStatus.MENUNGGU_PELUNASAN, phase__pelunasan_deadline__gt=now,
                                  phase__pelunasan_deadline__lte=now + PELUNASAN_REMINDER_BEFORE
                                  ).select_related("event", "phase")
    for order in orders:
        summary = settlement.summarize(order)
        count += bool(notify.enqueue(order, "PENGINGAT_PELUNASAN", extra={
            "nominal": summary.remaining_before_war, "batas_waktu": order.phase.pelunasan_deadline}))
    return count


def mark_late_pelunasan(now) -> tuple[int, int]:
    late = Order.objects.filter(status=OrderStatus.MENUNGGU_PELUNASAN, phase__pelunasan_deadline__lt=now)
    marked = late.filter(is_late_pelunasan=False).update(is_late_pelunasan=True)
    # Sudah lunas / dibatalkan / batas diundur → tanda dihapus
    cleared = (Order.objects.filter(is_late_pelunasan=True)
               .exclude(status=OrderStatus.MENUNGGU_PELUNASAN, phase__pelunasan_deadline__lt=now)
               .update(is_late_pelunasan=False))
    return marked, cleared


def close_phases(now) -> int:
    count = 0
    for phase in SalePhase.objects.filter(status=PhaseStatus.BUKA, order_close_at__lt=now).select_related("event"):
        phase.status = PhaseStatus.TUTUP
        phase.save(update_fields=["status", "updated_at"])
        audit.log("phase.auto_close", actor=Actor.system(), obj=phase, summary=f"Pemesanan ditutup otomatis: {phase}")
        count += 1
    return count


class Command(BaseCommand):
    help = "Tugas berkala Dreamtify (aman dijalankan berulang)."

    def handle(self, *args, **options):
        now = timezone.now()
        cancelled = cancel_expired_fees(now)
        fee_reminders = remind_fees(now)
        pelunasan_reminders = remind_pelunasan(now)
        marked, cleared = mark_late_pelunasan(now)
        expired_va = va.expire_vas(now)
        closed = close_phases(now)
        summary = (f"batal lewat batas fee: {cancelled}, pengingat fee: {fee_reminders}, "
                   f"pengingat pelunasan: {pelunasan_reminders}, tandai lewat pelunasan: {marked} "
                   f"(hapus tanda: {cleared}), VA kedaluwarsa: {expired_va}, tahap ditutup: {closed}")
        logger.info("run_periodic — %s", summary)
        self.stdout.write(f"[OK] {summary}")
