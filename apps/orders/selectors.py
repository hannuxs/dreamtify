"""Query baca yang efisien (prefetch, tanpa N+1) untuk dipakai view."""
from django.db.models import Prefetch, QuerySet

from apps.core.enums import OrderStatus, PaymentStatus

from .models import Order, OrderLine, OrderTimeline, Payment, TicketSlot


def _lines_prefetch() -> Prefetch:
    return Prefetch(
        "lines",
        queryset=OrderLine.objects.select_related("cat_primary", "cat_backup1", "cat_backup2").prefetch_related(
            Prefetch("slots", queryset=TicketSlot.objects.select_related("secured_category"))
        ),
    )


def order_detail_qs(*, public_timeline_only: bool = False) -> QuerySet:
    """Semua yang dibutuhkan halaman detail/lacak pesanan dalam ±7 query."""
    timeline = OrderTimeline.objects.all()
    if public_timeline_only:
        timeline = timeline.filter(is_public=True)
    return Order.objects.select_related("event", "phase").prefetch_related(
        _lines_prefetch(),
        Prefetch("payments", queryset=Payment.objects.select_related("destination_account")),
        "va_notices",
        Prefetch("timeline", queryset=timeline),
    )


def get_order(code: str, **kwargs) -> Order:
    return order_detail_qs(**kwargs).get(code=code)


def orders_for_phase(phase, statuses=None) -> QuerySet:
    qs = Order.objects.filter(phase=phase).select_related("event", "phase").prefetch_related(
        _lines_prefetch(), "payments")
    if statuses:
        qs = qs.filter(status__in=statuses)
    return qs.order_by("created_at", "id")


def waitlist(phase) -> QuerySet:
    return orders_for_phase(phase, [OrderStatus.WAITING_LIST])


def pending_payments() -> QuerySet:
    """Antrian verifikasi: bukti yang menunggu, terlama dulu."""
    return (Payment.objects.filter(status=PaymentStatus.MENUNGGU)
            .select_related("order", "order__event", "order__phase", "destination_account")
            .order_by("created_at", "id"))
