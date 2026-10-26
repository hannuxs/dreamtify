"""Kelola event (docs/05 §2): daftar, form bertab (simpan per tab), duplikat."""
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core import audit
from apps.core.enums import EventStatus, ServiceType
from apps.core.models import SiteSetting
from apps.events import services as event_services
from apps.events.models import Event, FeeRule

from .forms import (
    CategoryFormSet,
    EventInfoForm,
    EventRulesForm,
    FeeCopyForm,
    FeeMatrixForm,
    PhaseFormSet,
    PromotorForm,
)
from .permissions import admin_required, is_owner
from .views import actor_for, dash_render, saved

TABS = [
    ("info", "Info"),
    ("tahap", "Tahap & jadwal"),
    ("kategori", "Kategori"),
    ("fee", "Matriks fee"),
    ("aturan", "Aturan"),
    ("promotor", "Promotor"),
]
TAB_KEYS = {key for key, _ in TABS}


class SaveBlocked(Exception):
    """Simpan dibatalkan (rollback) — pesan untuk ditampilkan ke admin."""

    def __init__(self, messages_):
        super().__init__("; ".join(messages_))
        self.messages = messages_


def save_checked(event_pk, fn):
    """Jalankan `fn` dalam transaksi. Bila hasilnya membuat event TAMPIL + tahap BUKA
    tidak lengkap (validasi publikasi), semua perubahan dibatalkan."""
    with transaction.atomic():
        try:
            fn()
        except ProtectedError:
            raise SaveBlocked(["Data ini sudah dipakai pesanan sehingga tidak bisa dihapus. "
                               "Nonaktifkan saja."]) from None
        event = Event.objects.get(pk=event_pk)
        if event.status == EventStatus.TAMPIL:
            problems = event_services.publication_problems(event)
            if problems:
                raise SaveBlocked(["Event sedang Tampil, jadi tahap yang Buka harus lengkap:"] + problems)


def _changed(form) -> list[str]:
    return [str(form.fields[name].label or name) for name in form.changed_data if name in form.fields]


# ---------------------------------------------------------------------------
# Daftar & buat
# ---------------------------------------------------------------------------

@admin_required
def event_list(request):
    status = request.GET.get("status", "")
    events = Event.objects.annotate(n_orders=Count("orders", distinct=True)).prefetch_related("phases")
    if status in EventStatus.values:
        events = events.filter(status=status)
    else:
        status = ""
        events = events.exclude(status=EventStatus.ARSIP)
    return dash_render(request, "dashboard/events/list.html", {
        "events": events, "status": status, "statuses": EventStatus.choices,
    }, active="events")


@admin_required
def event_create(request):
    form = EventInfoForm(request.POST or None, request.FILES or None, initial={"status": EventStatus.DRAFT})
    form.fields.pop("status")  # event baru selalu Draf
    if request.method == "POST" and form.is_valid():
        site = SiteSetting.load()
        event = form.save(commit=False)
        event.slug = event.slug or event_services.unique_slug(event.name)
        event.status = EventStatus.DRAFT
        event.booking_slot_fee = site.default_booking_slot_fee
        event.fee_payment_window_hours = site.default_fee_payment_window_hours
        event.created_by = request.user
        event.save()
        audit.log("event.create", actor=actor_for(request), obj=event, summary=f"Event baru: {event.name}")
        messages.success(request, "Event dibuat. Lanjut isi tahap & jadwal.")
        return redirect("dashboard:event_edit", pk=event.pk, tab="tahap")
    return dash_render(request, "dashboard/events/edit.html", {
        "form": form, "tab": "info", "tabs": TABS, "creating": True,
    }, active="events")


@admin_required
@require_POST
def event_duplicate(request, pk):
    event = get_object_or_404(Event, pk=pk)
    copy = event_services.duplicate_event(event, actor=actor_for(request))
    messages.success(request, f"Event diduplikat sebagai \"{copy.name}\" (Draf). Ubah nama, tanggal & harga.")
    return redirect("dashboard:event_edit", pk=copy.pk, tab="info")


# ---------------------------------------------------------------------------
# Form bertab
# ---------------------------------------------------------------------------

def _tab_info(request, event, actor, owner, bound):
    form = EventInfoForm(request.POST if bound else None, request.FILES if bound else None, instance=event)
    if bound and form.is_valid():
        def apply():
            obj = form.save(commit=False)
            obj.slug = obj.slug or event_services.unique_slug(obj.name, exclude_pk=obj.pk)
            obj.save()
            audit.log("event.update", actor=actor, obj=obj, summary=f"Info event diubah: {', '.join(_changed(form))}",
                      data={"fields": form.changed_data})
        return {"form": form}, apply
    return {"form": form}, None


def _tab_tahap(request, event, actor, owner, bound):
    formset = PhaseFormSet(request.POST if bound else None, queryset=event.phases.all(), prefix="phase")
    if bound and formset.is_valid():
        def apply():
            for obj in formset.save(commit=False):
                obj.event = event
                obj.save()
            for obj in formset.deleted_objects:
                obj.delete()
            audit.log("event.phases", actor=actor, obj=event, summary="Tahap & jadwal diubah")
        return {"formset": formset}, apply
    return {"formset": formset}, None


def _tab_kategori(request, event, actor, owner, bound):
    formset = CategoryFormSet(request.POST if bound else None, queryset=event.categories.all(), prefix="cat")
    if bound and formset.is_valid():
        def apply():
            for obj in formset.save(commit=False):
                obj.event = event
                obj.save()
            for obj in formset.deleted_objects:
                obj.delete()
            audit.log("event.categories", actor=actor, obj=event, summary="Kategori tiket diubah")
        return {"formset": formset}, apply
    return {"formset": formset}, None


def _tab_fee(request, event, actor, owner, bound):
    phases = event.phases.prefetch_related("fee_rules")
    action = request.POST.get("action") if bound else None
    form = FeeMatrixForm(request.POST if bound and action != "copy" else None, event=event, phases=phases)
    copy_form = FeeCopyForm(request.POST if bound and action == "copy" else None, event=event, prefix="copy")
    ctx = {"form": form, "grid": form.bound_grid(), "copy_form": copy_form,
           "services": form.services, "show_copy": len(form.phases) > 1}
    if bound and action == "copy" and copy_form.is_valid():
        def apply():
            event_services.copy_fee_matrix(copy_form.cleaned_data["source"], copy_form.cleaned_data["target"],
                                           actor=actor)
        return ctx, apply
    if bound and action != "copy" and form.is_valid():
        def apply():
            for phase, service, tier, value in form.values():
                if value is None:
                    FeeRule.objects.filter(phase=phase, service_type=service, fee_tier=tier).delete()
                else:
                    FeeRule.objects.update_or_create(phase=phase, service_type=service, fee_tier=tier,
                                                     defaults={"fee_per_ticket": value})
            audit.log("event.fees", actor=actor, obj=event, summary="Matriks fee diubah")
        return ctx, apply
    return ctx, None


def _tab_aturan(request, event, actor, owner, bound):
    form = EventRulesForm(request.POST if bound else None, instance=event)
    if bound and form.is_valid():
        def apply():
            form.save()
            audit.log("event.rules", actor=actor, obj=event, summary=f"Aturan diubah: {', '.join(_changed(form))}",
                      data={"fields": form.changed_data})
        return {"form": form}, apply
    return {"form": form}, None


def _tab_promotor(request, event, actor, owner, bound):
    if bound and request.POST.get("action") == "regenerate":
        def apply():
            event_services.regenerate_promotor_token(event, actor=actor)
        return {"form": PromotorForm(instance=event, owner=owner)}, apply
    form = PromotorForm(request.POST if bound else None, instance=event, owner=owner)
    if bound and form.is_valid():
        def apply():
            form.save()
            audit.log("event.promotor", actor=actor, obj=event, summary=f"Promotor diubah: {', '.join(_changed(form))}",
                      data={"fields": form.changed_data})
        return {"form": form}, apply
    return {"form": form}, None


HANDLERS = {
    "info": _tab_info, "tahap": _tab_tahap, "kategori": _tab_kategori,
    "fee": _tab_fee, "aturan": _tab_aturan, "promotor": _tab_promotor,
}
SAVED_MESSAGES = {
    "info": "Info event tersimpan.", "tahap": "Tahap & jadwal tersimpan.", "kategori": "Kategori tersimpan.",
    "fee": "Matriks fee tersimpan.", "aturan": "Aturan tersimpan.", "promotor": "Pengaturan promotor tersimpan.",
}


def _render_edit(request, event, tab, tab_ctx, *, blocked=None, toast=None, status=200):
    event.refresh_from_db()
    ctx = {
        "event": event, "tab": tab, "tabs": TABS,
        "checklist": event_services.checklist(event),
        "public_url": request.build_absolute_uri(reverse("public:event_detail", args=[event.slug])),
        "promotor_url": request.build_absolute_uri(f"/p/{event.promotor_token}/"),
        "blocked": blocked or [],
        "is_owner": is_owner(request.user),
        "service_labels": dict(ServiceType.choices),
    }
    ctx.update(tab_ctx)
    return dash_render(request, "dashboard/events/edit.html", ctx, active="events", status=status, toast=toast)


@admin_required
def event_edit(request, pk, tab="info"):
    event = get_object_or_404(Event, pk=pk)
    if tab not in TAB_KEYS:
        raise Http404
    actor = actor_for(request)
    owner = is_owner(request.user)
    handler = HANDLERS[tab]
    bound = request.method == "POST"
    tab_ctx, apply = handler(request, event, actor, owner, bound)

    if bound and apply is not None:
        try:
            save_checked(event.pk, apply)
        except SaveBlocked as exc:
            return _render_edit(request, event, tab, tab_ctx, blocked=exc.messages)
        message = SAVED_MESSAGES[tab]
        if tab == "promotor" and request.POST.get("action") == "regenerate":
            message = "Link promotor diganti. Link lama tidak berlaku lagi."
        if tab == "fee" and request.POST.get("action") == "copy":
            message = "Matriks fee disalin."
        url = reverse("dashboard:event_edit", args=[event.pk, tab])
        return saved(request, message, url,
                     lambda msg: _render_edit(request, event, tab, handler(request, event, actor, owner, False)[0],
                                              toast=msg))
    return _render_edit(request, event, tab, tab_ctx)
