"""
Tugas berkala (tiap 15 menit; docs/02 §7). Semua langkah idempoten.

Versi fase 06: (1) batalkan MENUNGGU_FEE lewat batas, (4) tandai lewat batas
pelunasan, (6) tutup tahap yang waktu pesannya lewat. Pengingat (2, 3) &
VA kedaluwarsa (5) ditambahkan di fase 07/09.
"""
import logging

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.core import audit
from apps.core.actors import Actor
from apps.core.enums import OrderStatus, PhaseStatus
from apps.events.models import SalePhase
from apps.orders.models import Order
from apps.orders.services import transitions

logger = logging.getLogger("dreamtify.periodic")


def cancel_expired_fees(now) -> int:
    count = 0
    for order in Order.objects.filter(status=OrderStatus.MENUNGGU_FEE, fee_deadline__lt=now).only("pk"):
        if transitions.cancel_expired_fee(order, now=now):
            count += 1
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
        marked, cleared = mark_late_pelunasan(now)
        closed = close_phases(now)
        summary = (f"batal lewat batas fee: {cancelled}, tandai lewat pelunasan: {marked} (hapus tanda: {cleared}), "
                   f"tahap ditutup: {closed}")
        logger.info("run_periodic — %s", summary)
        self.stdout.write(f"[OK] {summary}")
