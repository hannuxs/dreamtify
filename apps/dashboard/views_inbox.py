"""Kotak Kabar (docs/05 §9) & Template pesan (docs/05 §12)."""
from django import forms
from django.contrib import messages
from django.core.paginator import Paginator
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core import audit
from apps.core.enums import NotificationChannel, NotificationStatus
from apps.core.forms import StyledFormMixin
from apps.events.models import Event
from apps.notifications import services as notify
from apps.notifications.defaults import DEFAULT_TEMPLATES
from apps.notifications.models import MessageTemplate, Notification
from apps.orders.models import Order
from apps.orders.services import guidance

from .permissions import admin_required, owner_required
from .views import actor_for, dash_render

TABS = [("perlu", "Perlu dikirim"), ("terkirim", "Terkirim"), ("dilewati", "Dilewati"), ("email", "Email")]


def _filtered(request, tab="perlu"):
    qs = Notification.objects.select_related("order__event", "order__phase", "sent_by")
    if tab == "email":
        qs = qs.filter(channel=NotificationChannel.EMAIL)
    else:
        qs = qs.filter(channel=NotificationChannel.WA, status={
            "perlu": NotificationStatus.PERLU_DIKIRIM, "terkirim": NotificationStatus.TERKIRIM,
            "dilewati": NotificationStatus.DILEWATI}.get(tab, NotificationStatus.PERLU_DIKIRIM))
    event = request.GET.get("event") or ""
    key = request.GET.get("key") or ""
    if event.isdigit():
        qs = qs.filter(order__event_id=int(event))
    if key in DEFAULT_TEMPLATES:
        qs = qs.filter(template_key=key)
    order_by = ("created_at", "id") if tab == "perlu" else ("-created_at", "-id")
    params = {k: v for k, v in (("event", event), ("key", key)) if v}
    return qs.order_by(*order_by), params


def _titles():
    titles = {k: v[0] for k, v in DEFAULT_TEMPLATES.items()}
    titles.update(dict(MessageTemplate.objects.values_list("key", "title")))
    return titles


@admin_required
def inbox(request):
    tab = request.GET.get("tab", "perlu")
    tab = tab if tab in dict(TABS) else "perlu"
    qs, params = _filtered(request, tab)
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    titles = _titles()
    rows = [{"n": n, "title": titles.get(n.template_key, n.template_key)} for n in page]
    return dash_render(request, "dashboard/inbox.html", {
        "tab": tab, "tabs": TABS, "page": page, "rows": rows, "params": params,
        "events": Event.objects.order_by("-first_show_date"), "keys": sorted(titles.items(), key=lambda kv: kv[1]),
        "pending_total": Notification.objects.filter(channel=NotificationChannel.WA,
                                                     status=NotificationStatus.PERLU_DIKIRIM).count(),
    }, active="inbox")


@admin_required
def inbox_send(request, pk):
    """Buka wa.me (tab baru) sekaligus tandai TERKIRIM."""
    notification = get_object_or_404(Notification, pk=pk, channel=NotificationChannel.WA)
    notify.mark_sent(notification, user=request.user)
    return HttpResponseRedirect(notify.wa_url(notification))


def _back(request, fallback):
    target = request.POST.get("next", "")
    return redirect(target if target.startswith("/kelola/") else fallback)


@admin_required
@require_POST
def inbox_skip(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    notify.mark_skipped(notification, user=request.user)
    messages.info(request, "Kabar dilewati.")
    return _back(request, reverse("dashboard:inbox"))


@admin_required
@require_POST
def inbox_edit(request, pk):
    notification = get_object_or_404(Notification, pk=pk, status=NotificationStatus.PERLU_DIKIRIM)
    notify.update_text(notification, request.POST.get("text", ""))
    messages.success(request, "Pesan diubah.")
    return _back(request, reverse("dashboard:inbox"))


@admin_required
def inbox_sequence(request):
    """Mode beruntun: satu pesan per layar, "Kirim & lanjut"."""
    qs, params = _filtered(request, "perlu")
    current = qs.first()
    titles = _titles()
    return dash_render(request, "dashboard/inbox_sequence.html", {
        "current": current, "title": titles.get(current.template_key, "") if current else "",
        "remaining": qs.count(), "params": params, "self_url": request.get_full_path(),
    }, active="inbox")


@admin_required
@require_POST
def order_message(request, code):
    """Buat kabar manual dari detail pesanan, lalu langsung tampil tombol kirim."""
    order = get_object_or_404(Order.objects.select_related("event", "phase"), code=code)
    key = request.POST.get("key", "")
    if key not in guidance.MANUAL_MESSAGE_KEYS:
        messages.error(request, "Jenis kabar tidak dikenal.")
    else:
        n = notify.enqueue_manual(order, key, actor_label=request.user.get_username(),
                                  extra=guidance.message_extra(order, key))
        if n:
            audit.log("notification.manual", actor=actor_for(request), obj=order, summary=f"{order.code}: kabar {key} dibuat")
            messages.success(request, "Kabar disiapkan — tekan Kirim WA di bagian Kabar.")
        else:
            messages.error(request, "Template ini sedang nonaktif atau nomor WA kosong.")
    return redirect(reverse("dashboard:order_detail", args=[order.code]) + "#kabar")


# ---------------------------------------------------------------------------
# Template pesan (Owner)
# ---------------------------------------------------------------------------

class TemplateForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = MessageTemplate
        fields = ["title", "body", "is_active", "send_email"]
        widgets = {"body": forms.Textarea(attrs={"rows": 12})}


@owner_required
def template_edit(request, key):
    if key not in DEFAULT_TEMPLATES:
        return redirect("dashboard:settings_tab", tab="template")
    title, body, send_email = DEFAULT_TEMPLATES[key]
    tpl, _ = MessageTemplate.objects.get_or_create(key=key, defaults={"title": title, "body": body,
                                                                      "send_email": send_email})
    form = TemplateForm(request.POST or None, instance=tpl)
    if request.method == "POST":
        if request.POST.get("action") == "default":
            tpl.title, tpl.body, tpl.send_email, tpl.is_customized = title, body, send_email, False
            tpl.save()
            audit.log("template.reset", actor=actor_for(request), obj=tpl, summary=f"Template {key} dikembalikan ke default")
            messages.success(request, "Template dikembalikan ke isi default.")
            return redirect("dashboard:template_edit", key=key)
        if form.is_valid():
            tpl = form.save(commit=False)
            tpl.is_customized = True
            tpl.save()
            audit.log("template.update", actor=actor_for(request), obj=tpl, summary=f"Template {key} diubah")
            messages.success(request, "Template tersimpan.")
            return redirect("dashboard:template_edit", key=key)
    current_body = form["body"].value() or ""
    return dash_render(request, "dashboard/template_edit.html", {
        "tpl": tpl, "form": form, "preview": notify.preview(current_body),
        "unknown": notify.unknown_placeholders(current_body), "known": sorted(notify.KNOWN_PLACEHOLDERS),
        "email_only": key in ("PESANAN_DIBUAT", "WAITING_LIST_MASUK"),
    }, active="settings")
