"""Mode War (docs/05 §6) — dioptimalkan untuk HP. Semua perubahan lewat services."""
import json
import time

from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.enums import (
    EventStatus,
    NotificationChannel,
    NotificationStatus,
    OrderStatus,
    PhaseStatus,
    SlotResult,
    TicketPaymentMethod,
    VaSource,
    VaStatus,
)
from apps.core.forms import DATETIME_INPUT_FORMATS, DateTimeLocalInput, RupiahField, StyledFormMixin
from apps.events.models import SalePhase, TicketCategory
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderLine, TicketSlot, VaNotice
from apps.orders.services import transitions, va
from apps.orders.services.transitions import InvalidTransition, SlotConflict

from .permissions import admin_required
from .views import actor_for, dash_render

WAR_VISIBLE = (OrderStatus.SIAP_WAR, OrderStatus.PROSES_WAR, OrderStatus.PENYELESAIAN, OrderStatus.SELESAI)
VA_METHODS = (TicketPaymentMethod.VA_BCA, TicketPaymentMethod.VA_MANDIRI)
FILTERS = [("semua", "Semua"), ("belum", "Belum diisi"), ("va", "VA"), ("titip", "Titip bayar"),
           ("jaswar", "JASWAR"), ("jastip", "JASTIP")]
# ASUMSI: jendela undo 10 detik di layar; setelahnya hasil tetap bisa dikoreksi lewat "Ubah hasil" selama war
UNDO_SECONDS = 10


class VaForm(StyledFormMixin, forms.Form):
    bank = forms.CharField(label="Bank", max_length=50)
    va_number = forms.CharField(label="Nomor VA", max_length=64, widget=forms.TextInput(attrs={"inputmode": "numeric"}))
    amount = RupiahField(label="Nominal (Rp)")
    expires_at = forms.DateTimeField(label="Bayar sebelum", required=False, widget=DateTimeLocalInput(),
                                     input_formats=DATETIME_INPUT_FORMATS)
    slots = forms.MultipleChoiceField(label="Tiket yang dicakup", required=False, widget=forms.CheckboxSelectMultiple)
    note = forms.CharField(label="Catatan", required=False, max_length=200)

    def __init__(self, *args, order, **kwargs):
        initial = kwargs.pop("initial", {}) or {}
        initial.setdefault("bank", "BCA" if order.ticket_payment_method == TicketPaymentMethod.VA_BCA else "Mandiri")
        super().__init__(*args, initial=initial, prefix=f"va{order.pk}", **kwargs)
        self.fields["slots"].choices = [
            (s.pk, f"{line.holder_name} · tiket {s.index}") for line in order.lines.all() for s in line.slots.all()]
        self.fields["slots"].initial = [c[0] for c in self.fields["slots"].choices]


def _orders(phase, flt):
    qs = (Order.objects.filter(phase=phase, status__in=WAR_VISIBLE).select_related("event", "phase")
          .prefetch_related(
              Prefetch("lines", queryset=OrderLine.objects.select_related("cat_primary", "cat_backup1", "cat_backup2")
                       .prefetch_related(Prefetch("slots", queryset=TicketSlot.objects.select_related("secured_category")))),
              Prefetch("va_notices", queryset=VaNotice.objects.order_by("-created_at")),
              Prefetch("notifications", queryset=Notification.objects.filter(
                  template_key="VA_DIKIRIM", channel=NotificationChannel.WA)),
          ).order_by("created_at", "id"))
    if phase.status in (PhaseStatus.WAR, PhaseStatus.SELESAI):
        qs = qs.exclude(status=OrderStatus.SIAP_WAR)
    if flt == "belum":
        qs = qs.filter(lines__slots__result=SlotResult.MENUNGGU).distinct()
    elif flt == "va":
        qs = qs.filter(ticket_payment_method__in=VA_METHODS)
    elif flt == "titip":
        qs = qs.filter(ticket_payment_method=TicketPaymentMethod.TITIP_BAYAR)
    elif flt in ("jaswar", "jastip"):
        qs = qs.filter(lines__service_type=flt.upper()).distinct()
    return qs


def _counts(phase) -> dict:
    agg = TicketSlot.objects.filter(
        line__order__phase=phase,
        line__order__status__in=(OrderStatus.PROSES_WAR, OrderStatus.PENYELESAIAN, OrderStatus.SELESAI),
    ).aggregate(
        total=Count("pk"),
        secured=Count("pk", filter=Q(result=SlotResult.SECURED)),
        failed=Count("pk", filter=Q(result__in=(SlotResult.GAGAL, SlotResult.GAGAL_CUSTOMER))),
        pending=Count("pk", filter=Q(result=SlotResult.MENUNGGU)),
    )
    return agg


def _card_ctx(order, phase, categories, *, undo_slot=None, va_form=None):
    pending_va_msgs = {n.dedupe_key.split(":")[2]: n for n in order.notifications.all()
                       if n.status == NotificationStatus.PERLU_DIKIRIM and n.dedupe_key.count(":") >= 3}
    vas = [{"va": v, "notification": pending_va_msgs.get(str(v.pk))} for v in order.va_notices.all()
           if v.source == VaSource.ADMIN]
    lines = []
    for line in order.lines.all():
        choices = [("primary", "Utama", line.cat_primary), ("backup1", "Cad 1", line.cat_backup1),
                   ("backup2", "Cad 2", line.cat_backup2)]
        lines.append({"line": line, "choices": [c for c in choices if c[2]], "slots": list(line.slots.all())})
    is_va = order.ticket_payment_method in VA_METHODS
    return {
        "order": order, "lines": lines, "categories": categories, "vas": vas, "is_va": is_va,
        "can_edit": phase.status == PhaseStatus.WAR and order.status in (
            OrderStatus.PROSES_WAR, OrderStatus.PENYELESAIAN, OrderStatus.SELESAI),
        "va_form": va_form or (VaForm(order=order) if is_va and order.status == OrderStatus.PROSES_WAR else None),
        "undo_slot": undo_slot, "undo_until": int((time.time() + UNDO_SECONDS) * 1000) if undo_slot else 0,
    }


def _list_ctx(request, phase):
    flt = request.GET.get("f", "semua")
    flt = flt if flt in dict(FILTERS) else "semua"
    categories = list(TicketCategory.objects.filter(event=phase.event).order_by("sort_order"))
    orders = list(_orders(phase, flt))
    not_ready = list(Order.objects.filter(phase=phase, status__in=transitions.PAYMENT_STAGE)
                     .order_by("created_at").values_list("code", "status"))
    customer_vas = (VaNotice.objects.filter(order__phase=phase, source=VaSource.CUSTOMER,
                                            status__in=(VaStatus.AKTIF, VaStatus.DIKLAIM_CUSTOMER))
                    .select_related("order").order_by("created_at"))
    return {
        "phase": phase, "filters": FILTERS, "flt": flt, "counts": _counts(phase),
        "cards": [_card_ctx(o, phase, categories) for o in orders],
        "not_ready": not_ready, "customer_vas": customer_vas,
        "siap_count": sum(1 for o in orders if o.status == OrderStatus.SIAP_WAR),
    }


@admin_required
def war_index(request):
    phases = list(SalePhase.objects.select_related("event")
                  .filter(event__status__in=(EventStatus.DRAFT, EventStatus.TAMPIL))
                  .exclude(status=PhaseStatus.SELESAI).order_by("war_at"))
    live = [p for p in phases if p.status == PhaseStatus.WAR]
    if len(live) == 1:
        return redirect("dashboard:war_mode", phase_id=live[0].pk)
    return dash_render(request, "dashboard/war/index.html", {"phases": phases}, active="war")


@admin_required
def war_mode(request, phase_id):
    phase = get_object_or_404(SalePhase.objects.select_related("event"), pk=phase_id)
    ctx = _list_ctx(request, phase)
    ctx["refresh_url"] = reverse("dashboard:war_mode", args=[phase.pk]) + f"?f={ctx['flt']}"
    return dash_render(request, "dashboard/war/mode.html", ctx, active="war")


@admin_required
@require_POST
def war_start(request, phase_id):
    phase = get_object_or_404(SalePhase, pk=phase_id)
    try:
        result = transitions.start_war(phase, actor=actor_for(request))
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    else:
        msg = f"War dimulai: {len(result.started)} pesanan masuk Mode War."
        if result.not_ready:
            msg += f" {len(result.not_ready)} pesanan belum siap (tidak ikut)."
        messages.success(request, msg)
    return redirect("dashboard:war_mode", phase_id=phase.pk)


@admin_required
@require_POST
def war_finish(request, phase_id):
    phase = get_object_or_404(SalePhase, pk=phase_id)
    try:
        marked = transitions.finish_war(phase, actor=actor_for(request),
                                        mark_rest_failed=request.POST.get("mark_rest") == "1")
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "War selesai." + (f" {marked} tiket ditandai Gagal." if marked else ""))
    return redirect("dashboard:war_mode", phase_id=phase.pk)


def _render_card(request, order_pk, *, toast, tone="success", undo_slot=None, va_form=None, status=200):
    order = _orders_one(order_pk)
    categories = list(TicketCategory.objects.filter(event_id=order.event_id).order_by("sort_order"))
    response = dash_render(request, "dashboard/war/_order_card.html",
                           _card_ctx(order, order.phase, categories, undo_slot=undo_slot, va_form=va_form),
                           status=status)
    response["HX-Trigger"] = json.dumps({"dt:toast": {"message": toast, "tone": tone}})
    return response


def _orders_one(order_pk):
    order = Order.objects.get(pk=order_pk)
    return _orders(order.phase, "semua").get(pk=order_pk) if order.status in WAR_VISIBLE else order


@admin_required
@require_POST
def war_slot(request, slot_id):
    """Simpan hasil satu tiket (satu ketukan) atau undo. Mengembalikan kartu pesanan."""
    slot = get_object_or_404(TicketSlot.objects.select_related("line__order"), pk=slot_id)
    line, order = slot.line, slot.line.order
    pick = request.POST.get("pick", "")
    category, result = None, SlotResult.SECURED
    if pick in ("primary", "backup1", "backup2"):
        category = getattr(line, f"cat_{pick}")
    elif pick == "other":
        category = TicketCategory.objects.filter(event_id=order.event_id, pk=request.POST.get("other") or 0).first()
    elif pick == "gagal":
        result = SlotResult.GAGAL
    elif pick == "gagal_customer":
        result = SlotResult.GAGAL_CUSTOMER
    elif pick == "undo":
        result = SlotResult.MENUNGGU
    else:
        return _render_card(request, order.pk, toast="Pilihan tidak dikenal.", tone="danger")
    try:
        version = int(request.POST.get("version", ""))
    except ValueError:
        version = None
    try:
        transitions.set_slot_result(slot, result, actor=actor_for(request), category=category,
                                    ticket_reference=request.POST.get("ticket_reference", ""), expected_version=version)
    except SlotConflict:
        return _render_card(request, order.pk, tone="danger",
                            toast="Tiket ini baru diubah admin lain — data terbaru ditampilkan, cek lalu ulangi.")
    except (InvalidTransition, ValidationError) as exc:
        msg = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
        return _render_card(request, order.pk, toast=msg, tone="danger")
    label = {"undo": "Dibatalkan (undo)", "gagal": "Gagal", "gagal_customer": "Gagal (customer)"}.get(
        pick, f"Dapat {category.name if category else ''}")
    return _render_card(request, order.pk, toast=f"{order.code} tiket {slot.index}: {label}",
                        undo_slot=None if pick == "undo" else slot.pk)


@admin_required
@require_POST
def war_va(request, code):
    order = get_object_or_404(Order.objects.select_related("phase"), code=code)
    full = _orders_one(order.pk)
    form = VaForm(request.POST, order=full)
    if not form.is_valid():
        return _render_card(request, order.pk, toast="Periksa isian VA.", tone="danger", va_form=form)
    d = form.cleaned_data
    try:
        va.create_va_notice(order, bank=d["bank"], va_number=d["va_number"], amount=d["amount"],
                            expires_at=d["expires_at"], slot_ids=[int(s) for s in d["slots"]], note=d["note"],
                            actor=actor_for(request))
    except (InvalidTransition, ValidationError) as exc:
        if isinstance(exc, ValidationError):
            for field, errors in exc.message_dict.items():
                for e in errors:
                    form.add_error(field if field in form.fields else None, e)
            return _render_card(request, order.pk, toast="Periksa isian VA.", tone="danger", va_form=form)
        return _render_card(request, order.pk, toast=str(exc), tone="danger")
    return _render_card(request, order.pk, toast="VA tersimpan & tampil di halaman customer. Kirim WA-nya ↓")


@admin_required
@require_POST
def war_va_paid(request, va_id):
    notice = get_object_or_404(VaNotice.objects.select_related("order"), pk=va_id)
    htmx = request.headers.get("HX-Request") == "true"
    try:
        va.mark_va_paid(notice, actor=actor_for(request))
    except InvalidTransition as exc:
        if htmx:
            return _render_card(request, notice.order_id, toast=str(exc), tone="danger")
        messages.error(request, str(exc))
    else:
        if htmx:
            return _render_card(request, notice.order_id, toast=f"{notice.order.code}: VA lunas.")
        messages.success(request, f"{notice.order.code}: VA ditandai lunas.")
    return redirect("dashboard:war_mode", phase_id=notice.order.phase_id)

