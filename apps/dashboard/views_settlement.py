"""Penyelesaian (refund & kekurangan, docs/05 §7) dan Penyerahan (docs/05 §8)."""
from django import forms
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core import audit
from apps.core.enums import FulfillmentStatus, HandoverMethod, ServiceType
from apps.core.forms import DateInput, RupiahField, StyledFormMixin
from apps.core.phone import to_local
from apps.core.uploads import ACCEPT_ATTR, process_private_upload
from apps.events.models import Event
from apps.exports.excel import xlsx_response
from apps.notifications import services as notify
from apps.orders.models import Order, TicketSlot
from apps.orders.selectors import handover_slots, refund_queue, shortfall_queue
from apps.orders.services import settlement, transitions
from apps.orders.services.transitions import InvalidTransition

from .permissions import admin_required
from .views import actor_for, dash_render

REMIND_KEYS = {"rekening": "REFUND_ISI_REKENING", "kekurangan": "KEKURANGAN_BAYAR"}


class RefundRecordForm(StyledFormMixin, forms.Form):
    amount = RupiahField(label="Nominal refund (Rp)")
    transfer_date = forms.DateField(label="Tanggal transfer", widget=DateInput())
    proof = forms.FileField(label="Bukti transfer refund", required=False,
                            widget=forms.ClearableFileInput(attrs={"accept": ACCEPT_ATTR}))
    note = forms.CharField(label="Catatan (tampil ke customer)", required=False, max_length=200)

    def clean_proof(self):
        proof = self.cleaned_data.get("proof")
        return process_private_upload(proof, name="refund") if proof else None


class HandoverForm(StyledFormMixin, forms.Form):
    action = forms.ChoiceField(choices=[
        ("ditukar", "Tandai gelang sudah ditukar"),
        ("siap", "Set siap diserahkan"),
        ("diserahkan", "Tandai sudah diserahkan"),
        ("info", "Kirim info penukaran (JASWAR)"),
    ], label="Aksi")
    method = forms.ChoiceField(label="Metode penyerahan", required=False,
                               choices=[("", "—")] + HandoverMethod.choices)
    detail = forms.CharField(label="Jadwal / lokasi / no. resi", required=False, max_length=300)
    receiver_name = forms.CharField(label="Nama penerima", required=False, max_length=150)
    note = forms.CharField(label="Catatan untuk customer", required=False, max_length=300)
    photo = forms.FileField(label="Foto (opsional)", required=False,
                            widget=forms.ClearableFileInput(attrs={"accept": ACCEPT_ATTR}))
    eticket = forms.FileField(label="E-tiket (opsional, untuk 1 tiket)", required=False,
                              widget=forms.ClearableFileInput(attrs={"accept": ACCEPT_ATTR}))

    def clean_photo(self):
        f = self.cleaned_data.get("photo")
        return process_private_upload(f, name="serah") if f else None

    def clean_eticket(self):
        f = self.cleaned_data.get("eticket")
        return process_private_upload(f, name="etiket") if f else None


ACTION_STATUS = {
    "ditukar": FulfillmentStatus.DITUKAR, "siap": FulfillmentStatus.SIAP_DISERAHKAN,
    "diserahkan": FulfillmentStatus.DISERAHKAN, "info": FulfillmentStatus.INFO_DIKIRIM,
}


def _event_filter(request):
    pk = request.GET.get("event") or ""
    return Event.objects.filter(pk=pk).first() if pk.isdigit() else None


# ---------------------------------------------------------------------------
# Penyelesaian
# ---------------------------------------------------------------------------

@admin_required
def settlement_page(request):
    tab = request.GET.get("tab", "refund")
    event = _event_filter(request)
    rows = refund_queue(event) if tab == "refund" else shortfall_queue(event)
    # ASUMSI: Admin (bukan hanya Owner) melihat rekening penuh karena dia yang mentransfer; tiap tampilan diaudit
    if tab == "refund" and any(o.refund_account_number for o, _ in rows):
        audit.log("refund.view_accounts", actor=actor_for(request),
                  summary=f"Melihat rekening refund ({sum(1 for o, _ in rows if o.refund_account_number)} pesanan)")
    forms_by_order = {o.pk: RefundRecordForm(prefix=f"r{o.pk}", initial={
        "amount": s.refund_due, "transfer_date": timezone.localdate()}) for o, s in rows} if tab == "refund" else {}
    return dash_render(request, "dashboard/settlement.html", {
        "tab": tab, "event": event, "events": Event.objects.order_by("-first_show_date"),
        "rows": [(o, s, forms_by_order.get(o.pk)) for o, s in rows],
        "total": sum(s.refund_due if tab == "refund" else s.shortfall for _, s in rows),
    }, active="settlement")


@admin_required
@require_POST
def refund_record(request, code):
    order = get_object_or_404(Order, code=code)
    form = RefundRecordForm(request.POST, request.FILES, prefix=f"r{order.pk}")
    if form.is_valid():
        d = form.cleaned_data
        try:
            transitions.record_refund(order, amount=d["amount"], proof=d["proof"], transfer_date=d["transfer_date"],
                                      note=d["note"], actor=actor_for(request))
        except (InvalidTransition, ValidationError) as exc:
            messages.error(request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
        else:
            messages.success(request, f"Refund {order.code} dicatat. Kabar disiapkan di Kotak Kabar.")
    else:
        messages.error(request, "Periksa isian refund: " + "; ".join(e for errs in form.errors.values() for e in errs))
    return redirect(reverse("dashboard:settlement") + "?tab=refund")


@admin_required
@require_POST
def remind(request, code, kind):
    order = get_object_or_404(Order.objects.select_related("event", "phase"), code=code)
    key = REMIND_KEYS.get(kind)
    if not key:
        return redirect("dashboard:settlement")
    summary = settlement.summarize(order)
    amount = summary.refund_due if kind == "rekening" else summary.shortfall
    if notify.enqueue_manual(order, key, actor_label=request.user.get_username(), extra={"nominal": amount}):
        messages.success(request, f"Kabar untuk {order.code} disiapkan di Kotak Kabar.")
    return redirect(reverse("dashboard:settlement") + ("?tab=kekurangan" if kind == "kekurangan" else "?tab=refund"))


@admin_required
def refund_export(request):
    event = _event_filter(request)
    rows = [[o.code, o.buyer_name, o.refund_bank_name, o.refund_account_number, o.refund_account_holder,
             s.refund_due, o.event.name] for o, s in refund_queue(event)]
    audit.log("export.refund", actor=actor_for(request), summary=f"Ekspor daftar refund ({len(rows)} baris)",
              data={"event": event.pk if event else None})
    return xlsx_response("Dreamtify_refund", [(
        "Refund", ["Kode", "Nama pemesan", "Bank", "No. rekening", "Atas nama", "Nominal", "Event"], rows, {3})])


# ---------------------------------------------------------------------------
# Penyerahan
# ---------------------------------------------------------------------------

@admin_required
def handover_page(request):
    event = _event_filter(request)
    service = request.GET.get("service") if request.GET.get("service") in ServiceType.values else None
    status = request.GET.get("status") if request.GET.get("status") in FulfillmentStatus.values else None
    include_done = request.GET.get("selesai") == "1"
    slots = list(handover_slots(event=event, service=service, status=status, include_done=include_done)[:500])
    shortfall_orders = {o.pk for o, _ in shortfall_queue(event)}
    return dash_render(request, "dashboard/handover.html", {
        "slots": slots, "event": event, "events": Event.objects.order_by("-first_show_date"),
        "service": service, "status": status, "include_done": include_done, "form": HandoverForm(),
        "shortfall_orders": shortfall_orders, "statuses": FulfillmentStatus.choices,
        "query": request.GET.urlencode(),
    }, active="handover")


@admin_required
@require_POST
def handover_action(request):
    form = HandoverForm(request.POST, request.FILES)
    ids = [int(i) for i in request.POST.getlist("slots") if i.isdigit()]
    back = reverse("dashboard:handover") + (f"?{request.POST.get('query')}" if request.POST.get("query") else "")
    if not ids:
        messages.error(request, "Pilih minimal satu tiket.")
        return redirect(back)
    if not form.is_valid():
        messages.error(request, "Periksa isian: " + "; ".join(e for errs in form.errors.values() for e in errs))
        return redirect(back)
    d = form.cleaned_data
    status = ACTION_STATUS[d["action"]]
    photo_bytes = d["photo"].read() if d["photo"] else None
    done, errors = 0, []
    for slot in TicketSlot.objects.filter(pk__in=ids).select_related("line__order"):
        # Satu salinan file per tiket (ContentFile yang sama tidak bisa disimpan berulang)
        photo = ContentFile(photo_bytes, name=d["photo"].name) if photo_bytes else None
        try:
            # ASUMSI: e-tiket per orang berbeda → hanya dilampirkan bila tepat 1 tiket dipilih
            transitions.set_fulfillment(slot, status, actor=actor_for(request), method=d["method"],
                                        detail=d["detail"], receiver_name=d["receiver_name"], note=d["note"],
                                        photo=photo, eticket=d["eticket"] if len(ids) == 1 else None)
            done += 1
        except (InvalidTransition, ValidationError) as exc:
            msg = "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)
            errors.append(f"{slot.line.order.code} tiket {slot.index}: {msg}")
    if done:
        messages.success(request, f"{done} tiket diperbarui. Kabar disiapkan di Kotak Kabar.")
    for e in errors[:5]:
        messages.error(request, e)
    return redirect(back)


@admin_required
def handover_export(request):
    event = _event_filter(request)
    rows = []
    for slot in handover_slots(event=event, service=ServiceType.JASTIP, include_done=True):
        order, line = slot.line.order, slot.line
        rows.append([order.code, line.holder_name, to_local(line.holder_whatsapp or order.buyer_whatsapp),
                     slot.secured_category.name, slot.index, slot.get_fulfillment_status_display(),
                     slot.get_handover_method_display() if slot.handover_method else "", slot.handover_detail, ""])
    audit.log("export.handover", actor=actor_for(request), summary=f"Ekspor daftar penyerahan gelang ({len(rows)} tiket)")
    return xlsx_response("Dreamtify_penyerahan_gelang", [(
        "Penyerahan", ["Kode", "Pemegang", "No WA", "Kategori", "Tiket ke-", "Status", "Metode", "Detail",
                       "Tanda tangan penerima"], rows, {2})])
