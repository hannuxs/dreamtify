"""Antrian verifikasi pembayaran (docs/05 §4) & waiting list (docs/05 §5)."""
from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.enums import CancelReason, EventStatus, OrderStatus, PaymentKind, PaymentStatus, PhaseStatus
from apps.core.forms import RupiahField, StyledFormMixin
from apps.events.models import Event, SalePhase
from apps.orders.models import Order, Payment
from apps.orders.selectors import get_order, pending_payments
from apps.orders.services import guidance, quota, settlement, transitions
from apps.orders.services.transitions import InvalidTransition

from .permissions import admin_required
from .views import actor_for, dash_render

QUICK_REASONS = ["Bukti tidak terbaca", "Nominal tidak sesuai", "Dana belum masuk", "Rekening tujuan salah"]


class AcceptForm(StyledFormMixin, forms.Form):
    amount_received = RupiahField(label="Nominal diterima (Rp)")


class RejectForm(StyledFormMixin, forms.Form):
    reason = forms.CharField(label="Alasan ditolak", max_length=300,
                             widget=forms.Textarea(attrs={"rows": 2, "placeholder": "Wajib diisi — dikirim ke customer"}))


def _filtered(request):
    qs = pending_payments()
    event = request.GET.get("event") or ""
    kind = request.GET.get("kind") or ""
    if event.isdigit():
        qs = qs.filter(order__event_id=int(event))
    if kind in PaymentKind.values:
        qs = qs.filter(kind=kind)
    return qs, {k: v for k, v in (("event", event), ("kind", kind)) if v}


def _queue_url(params, pk=None):
    query = dict(params)
    if pk:
        query["p"] = pk
    return reverse("dashboard:verify_queue") + (f"?{urlencode(query)}" if query else "")


@admin_required
def verify_queue(request):
    qs, params = _filtered(request)
    items = list(qs[:200])
    current = None
    wanted = request.GET.get("p")
    if wanted and wanted.isdigit():
        current = next((p for p in items if p.pk == int(wanted)), None)
    current = current or (items[0] if items else None)
    ctx = {"items": items, "current": current, "params": params, "params_qs": urlencode(params),
           "quick_reasons": QUICK_REASONS,
           "events": Event.objects.exclude(status=EventStatus.ARSIP), "kinds": PaymentKind.choices[:3]}
    if current:
        idx = items.index(current)
        order = get_order(current.order.code)
        summary = settlement.summarize(order)
        expected, alt = guidance.expected_amounts(order, current.kind, summary)
        ctx.update({
            "order": order, "summary": summary, "expected": expected, "expected_alt": alt,
            "diff": current.amount_claimed - expected,
            "is_pdf": current.proof.name.lower().endswith(".pdf") if current.proof else False,
            "prev_url": _queue_url(params, items[idx - 1].pk) if idx > 0 else "",
            "next_url": _queue_url(params, items[idx + 1].pk) if idx + 1 < len(items) else "",
            "accept_form": AcceptForm(initial={"amount_received": current.amount_claimed}),
            "reject_form": RejectForm(),
            "other_pending": [p for p in order.payments.all() if p.status == PaymentStatus.MENUNGGU and p.pk != current.pk],
        })
    return dash_render(request, "dashboard/verify.html", ctx, active="verify")


@admin_required
@require_POST
def verify_action(request, pk):
    payment = get_object_or_404(Payment, pk=pk)
    qs, params = _filtered(request)
    ids = list(qs.values_list("pk", flat=True)[:200])
    if payment.pk in ids:  # bukti berikutnya setelah yang ini (memutar ke awal)
        i = ids.index(payment.pk)
        ids = ids[i + 1:] + ids[:i]
    next_pk = ids[0] if ids else None
    actor = actor_for(request)
    action = request.POST.get("action")
    try:
        if action == "terima":
            form = AcceptForm(request.POST)
            if not form.is_valid():
                raise ValidationError("Nominal diterima tidak valid.")
            transitions.verify_payment(payment, actor=actor, amount_received=form.cleaned_data["amount_received"])
            messages.success(request, f"{payment.order.code}: pembayaran diterima.")
        elif action == "tolak":
            transitions.reject_payment(payment, actor=actor, reason=request.POST.get("reason", ""))
            messages.success(request, f"{payment.order.code}: bukti ditolak, kabar disiapkan.")
        else:
            raise ValidationError("Aksi tidak dikenal.")
    except (InvalidTransition, ValidationError) as exc:
        messages.error(request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
        return redirect(_queue_url(params, payment.pk))
    return redirect(_queue_url(params, next_pk))


# ---------------------------------------------------------------------------
# Waiting list & lewat batas pelunasan
# ---------------------------------------------------------------------------

@admin_required
def waitlist(request):
    now = timezone.now()
    phases = (SalePhase.objects.select_related("event")
              .filter(event__status__in=(EventStatus.DRAFT, EventStatus.TAMPIL))
              .exclude(status=PhaseStatus.SELESAI).order_by("war_at", "event__name"))
    blocks = []
    for phase in phases:
        waiting = list(Order.objects.filter(phase=phase, status=OrderStatus.WAITING_LIST)
                       .prefetch_related("lines").order_by("created_at"))
        late = []
        if phase.pelunasan_deadline and phase.pelunasan_deadline < now:
            late = list(Order.objects.filter(phase=phase, status=OrderStatus.MENUNGGU_PELUNASAN)
                        .select_related("event", "phase").prefetch_related("lines__slots", "payments")
                        .order_by("created_at"))
        left = quota.remaining(phase)
        blocks.append({
            "phase": phase, "used": quota.used_tickets(phase), "remaining": left,
            "waiting": [{"order": o, "tickets": sum(ln.quantity for ln in o.lines.all()),
                         "fits": left is None or left >= sum(ln.quantity for ln in o.lines.all())} for o in waiting],
            "late": [{"order": o, "preview": settlement.cancellation_preview(o, CancelReason.LEWAT_BATAS_PELUNASAN)}
                     for o in late],
        })
    blocks = [b for b in blocks if b["waiting"] or b["late"] or b["phase"].slot_quota]
    return dash_render(request, "dashboard/waitlist.html", {"blocks": blocks}, active="waitlist")
