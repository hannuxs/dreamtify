"""Rekap & Ekspor (docs/05 §10, docs/07)."""
from django.core.exceptions import PermissionDenied
from django.http import Http404

from apps.core import audit
from apps.events.models import Event, SalePhase
from apps.exports import promotor, recap
from apps.exports.excel import xlsx_response
from apps.orders.selectors import orders_with_money
from apps.orders.services import settlement

from .permissions import admin_required, is_owner, owner_required
from .views import actor_for, dash_render

SUMMARY_HEADERS = ["Keterangan", "Nominal (Rp)"]
ORDER_HEADERS = ["Kode", "Tahap", "Pemesan", "Status", "Dibayar", "Refund keluar", "Tagihan final", "Pendapatan fee",
                 "Harga tiket", "Saldo tertahan", "Kekurangan"]


def _filters(request):
    """(event, tahap, termasuk_belum_bayar) dari query string."""
    pk = request.GET.get("event", "")
    event = Event.objects.filter(pk=pk).first() if pk.isdigit() else None
    phase_pk = request.GET.get("phase", "")
    phase = SalePhase.objects.filter(pk=phase_pk, event=event).first() if event and phase_pk.isdigit() else None
    return event, phase, request.GET.get("unpaid") == "1"


def _finance_rows(data) -> list:
    return [
        ("Fee diterima", data.fee_received),
        ("Pelunasan diterima (termasuk kekurangan)", data.pelunasan_received),
        ("Refund keluar", data.refund_out),
        ("Saldo tertahan", data.held),
        ("Kekurangan belum dibayar", data.shortfall),
        ("Harga tiket final (titip bayar)", data.ticket_price),
        ("Pendapatan fee final", data.fee_income),
    ]


@admin_required
def reports(request):
    events = list(Event.objects.all())
    event, phase, unpaid = _filters(request)
    event = event or (events[0] if events else None)
    ctx = {"events": events, "event": event, "phase": phase, "unpaid": unpaid, "is_owner": is_owner(request.user)}
    if event:
        ctx["phases"] = list(event.phases.all())
        lines = promotor.export_lines(event, phase, unpaid)
        ctx["recap"] = promotor.recap_for(event, lines)
        ctx["stats"] = recap.download_stats(event)
        if ctx["is_owner"]:
            data, _ = settlement.finance_recap(orders_with_money(event, phase))
            ctx["finance_rows"] = _finance_rows(data)
    return dash_render(request, "dashboard/reports.html", ctx, active="reports")


@admin_required
def promotor_export(request, fmt):
    if fmt not in ("xlsx", "csv"):
        raise Http404
    event, phase, unpaid = _filters(request)
    if event is None:
        raise Http404
    # Admin yang mengirim nik=1 tetap mendapat kolom tersembunyi
    include_nik = request.GET.get("nik") == "1" and is_owner(request.user)
    lines = promotor.export_lines(event, phase, unpaid)
    audit.log(recap.EXPORT_ACTION, actor=actor_for(request), obj=event,
              summary=f"Ekspor promotor {event.name} ({len(lines)} baris)",
              data={"via": "admin", "format": fmt, "phase": phase.name if phase else "", "include_nik": include_nik,
                    "include_unpaid": unpaid, "rows": len(lines)})
    return promotor.file_response(event, phase, lines, fmt, include_nik=include_nik, include_unpaid=unpaid)


@owner_required
def finance_export(request):
    event, phase, _ = _filters(request)
    if event is None:
        raise PermissionDenied
    data, rows = settlement.finance_recap(orders_with_money(event, phase))
    audit.log("export.finance", actor=actor_for(request), obj=event, summary=f"Ekspor rekap keuangan {event.name}")
    order_rows = [[r.order.code, r.order.phase.name, r.order.buyer_name, r.order.get_status_display(), r.summary.paid_in,
                   r.summary.refunded, r.summary.final_due, r.fee_income, r.ticket_price, r.held,
                   r.summary.shortfall if r.summary.results_final else 0] for r in rows]
    return xlsx_response(f"Dreamtify_keuangan_{event.slug}", [
        ("Ringkasan", SUMMARY_HEADERS, _finance_rows(data), set()),
        ("Per pesanan", ORDER_HEADERS, order_rows, set()),
    ])
