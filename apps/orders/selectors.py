"""Query baca yang efisien (prefetch, tanpa N+1) untuk dipakai view."""
from django.db.models import Prefetch, QuerySet

from apps.core.enums import INCOMING_PAYMENT_KINDS, FulfillmentStatus, OrderStatus, PaymentStatus, SlotResult

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


# ---------------------------------------------------------------------------
# Antrian penyelesaian (docs/05 §7–8)
# ---------------------------------------------------------------------------

def _with_money(qs):
    return (qs.filter(payments__kind__in=INCOMING_PAYMENT_KINDS, payments__status=PaymentStatus.DITERIMA)
            .distinct().select_related("event", "phase").prefetch_related(_lines_prefetch(), "payments"))


def orders_with_money(event, phase=None) -> QuerySet:
    qs = _with_money(Order.objects.filter(event=event))
    return qs.filter(phase=phase) if phase else qs


def refund_queue(event=None) -> list:
    """[(order, summary)] dengan SALDO > 0 setelah hasil final / batal (apa pun statusnya).
    ASUMSI: kelebihan bayar sebelum war diselesaikan setelah war (bukan masuk antrian)."""
    from .services import settlement

    qs = _with_money(Order.objects.exclude(status=OrderStatus.WAITING_LIST))
    if event:
        qs = qs.filter(event=event)
    rows = []
    for order in qs.order_by("created_at"):
        summary = settlement.summarize(order)
        if summary.results_final and summary.refund_due > 0:
            rows.append((order, summary))
    return rows


def shortfall_queue(event=None) -> list:
    """[(order, summary)] dengan kekurangan bayar setelah hasil war final."""
    from .services import settlement

    qs = _with_money(Order.objects.filter(status__in=(OrderStatus.PROSES_WAR, OrderStatus.PENYELESAIAN)))
    if event:
        qs = qs.filter(event=event)
    rows = []
    for order in qs.order_by("created_at"):
        summary = settlement.summarize(order)
        if summary.results_final and summary.shortfall > 0:
            rows.append((order, summary))
    return rows


def handover_slots(*, event=None, phase=None, service=None, status=None, include_done=False) -> QuerySet:
    """Tiket SECURED untuk halaman Penyerahan."""
    qs = (TicketSlot.objects.filter(result=SlotResult.SECURED)
          .select_related("line__order__event", "line__order__phase", "secured_category")
          .order_by("line__order__created_at", "line__sort_order", "index"))
    statuses = (OrderStatus.PENYELESAIAN, OrderStatus.SELESAI) if include_done else (OrderStatus.PENYELESAIAN,)
    qs = qs.filter(line__order__status__in=statuses)
    if event:
        qs = qs.filter(line__order__event=event)
    if phase:
        qs = qs.filter(line__order__phase=phase)
    if service:
        qs = qs.filter(line__service_type=service)
    if status:
        qs = qs.filter(fulfillment_status=status)
    elif not include_done:
        qs = qs.exclude(fulfillment_status__in=(FulfillmentStatus.DISERAHKAN, FulfillmentStatus.INFO_DIKIRIM))
    return qs
