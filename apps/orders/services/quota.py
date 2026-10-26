"""
Kuota slot per tahap — docs/02 §6.

Kuota dalam satuan tiket. Terpakai = Σ jumlah tiket pesanan berstatus
QUOTA_STATUSES. Pembuatan pesanan & "Naikkan dari waiting list" mengunci
baris SalePhase (`select_for_update`) supaya tidak terjadi rebutan.
Wajib dipanggil di dalam `transaction.atomic`.
"""
from django.db.models import Sum

from apps.core.enums import QUOTA_STATUSES
from apps.events.models import SalePhase


def lock_phase(phase_id) -> SalePhase:
    return SalePhase.objects.select_for_update().select_related("event").get(pk=phase_id)


def used_tickets(phase) -> int:
    from apps.orders.models import OrderLine

    total = OrderLine.objects.filter(
        order__phase_id=phase.pk, order__status__in=QUOTA_STATUSES
    ).aggregate(total=Sum("quantity"))["total"]
    return total or 0


def remaining(phase):
    """Sisa tiket; None = tanpa batas."""
    if phase.slot_quota is None:
        return None
    return max(0, phase.slot_quota - used_tickets(phase))


def can_fit(phase, quantity: int) -> bool:
    # ASUMSI: semua-atau-tidak. Pesanan 3 tiket dengan sisa 2 masuk waiting list utuh.
    left = remaining(phase)
    return left is None or left >= quantity
