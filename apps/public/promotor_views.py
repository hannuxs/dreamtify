"""Link rahasia promotor `/p/<token>/` (docs/07 §3): angka ringkas + unduh Excel/CSV, tanpa login."""
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from apps.core import audit, ratelimit
from apps.core.actors import Actor
from apps.core.enums import EventStatus
from apps.events.models import Event
from apps.exports import promotor, recap
from apps.orders.models import Payment
from apps.orders.services.links import check_promotor_file_signature

from .lacak_views import serve_private

DOWNLOAD_LIMIT = 30
DOWNLOAD_WINDOW = 3600


def _event_or_404(token) -> Event:
    # ASUMSI: event yang diarsip menutup link promotor walau masih dicentang aktif
    event = get_object_or_404(Event, promotor_token=token, promotor_link_enabled=True)
    if event.status == EventStatus.ARSIP:
        raise Http404
    return event


def _phase(request, event):
    pk = request.GET.get("tahap", "")
    return event.phases.filter(pk=pk).first() if pk.isdigit() else None


def _noindex(response):
    response["X-Robots-Tag"] = "noindex, nofollow"
    return response


def _page(request, event, phase, *, status=200, error=""):
    lines = promotor.export_lines(event, phase)
    return _noindex(render(request, "public/promotor.html", {
        "event": event, "phase": phase, "phases": list(event.phases.all()),
        "recap": promotor.recap_for(event, lines), "now": timezone.now(), "error": error,
        "query": f"?tahap={phase.pk}" if phase else "",
    }, status=status))


@never_cache
def promotor_page(request, token):
    event = _event_or_404(token)
    return _page(request, event, _phase(request, event))


@never_cache
def promotor_download(request, token, fmt):
    if fmt not in ("xlsx", "csv"):
        raise Http404
    event = _event_or_404(token)
    phase = _phase(request, event)
    if not ratelimit.hit("promotor", token, DOWNLOAD_LIMIT, DOWNLOAD_WINDOW):
        return _page(request, event, phase, status=429, error="Batas unduhan tercapai. Coba lagi sekitar 1 jam lagi.")
    lines = promotor.export_lines(event, phase)
    include_nik = event.promotor_include_nik
    audit.log(recap.EXPORT_ACTION, actor=Actor(label="link promotor", ip=ratelimit.client_ip(request)), obj=event,
              summary=f"Unduh promotor {event.name} ({len(lines)} baris)",
              data={"via": "link", "format": fmt, "phase": phase.name if phase else "", "include_nik": include_nik,
                    "rows": len(lines)})
    return _noindex(promotor.file_response(event, phase, lines, fmt, include_nik=include_nik))


@never_cache
def promotor_proof(request, token, payment_id):
    """Tanda tangan sudah mengikat token, jenis & id; event arsip ditolak di pemeriksaan tanda tangan."""
    event = get_object_or_404(Event, promotor_token=token)
    payment = get_object_or_404(Payment.objects.select_related("order"), pk=payment_id, order__event=event)
    if not payment.proof or not check_promotor_file_signature(event, "bukti", payment.pk, request.GET.get("s", "")):
        raise Http404
    return _noindex(serve_private(payment.proof, f"bukti-{payment.order.code}"))
