"""Pesanan di dashboard (docs/05 §3): daftar, detail, aksi kontekstual."""
import re

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.core import audit
from apps.core.crypto import digits_only, nik_hash
from apps.core.enums import (
    PRE_WAR_STATUSES,
    CancelReason,
    OrderStatus,
    PaymentStatus,
    ServiceType,
    TicketPaymentMethod,
)
from apps.core.forms import DateInput, RupiahField, StyledFormMixin
from apps.core.models import AuditLog, BankAccount
from apps.core.uploads import ACCEPT_ATTR, process_private_upload
from apps.events.models import Event, SalePhase
from apps.orders.models import Order, OrderLine, OrderTimeline
from apps.orders.selectors import order_detail_qs
from apps.orders.services import codes, guidance, settlement, transitions, updates
from apps.orders.services.links import tracking_url
from apps.orders.services.transitions import InvalidTransition
from apps.orders.services.validation import HolderData
from apps.public.forms import HolderEditForm

from .permissions import admin_required, is_owner
from .views import actor_for, dash_render

PAGE_SIZE = 25


# ---------------------------------------------------------------------------
# Form
# ---------------------------------------------------------------------------

class OrderFilterForm(StyledFormMixin, forms.Form):
    q = forms.CharField(label="Cari", required=False, widget=forms.TextInput(
        attrs={"placeholder": "Kode, nama, WA, email, pemegang, atau NIK lengkap"}))
    event = forms.ModelChoiceField(label="Event", queryset=Event.objects.all(), required=False, empty_label="Semua event")
    phase = forms.ModelChoiceField(label="Tahap", queryset=SalePhase.objects.select_related("event"), required=False,
                                   empty_label="Semua tahap")
    status = forms.MultipleChoiceField(label="Status", choices=OrderStatus.choices, required=False,
                                       widget=forms.CheckboxSelectMultiple)
    service = forms.ChoiceField(label="Layanan", required=False, choices=[("", "Semua layanan")] + ServiceType.choices)
    method = forms.ChoiceField(label="Metode bayar", required=False,
                               choices=[("", "Semua metode")] + TicketPaymentMethod.choices)
    late = forms.BooleanField(label="Lewat batas pelunasan", required=False)
    dup = forms.BooleanField(label="Peringatan NIK ganda", required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phase"].label_from_instance = lambda p: f"{p.event.name} – {p.name}"


class ManualPaymentForm(StyledFormMixin, forms.Form):
    amount = RupiahField(label="Nominal (Rp)")
    sender_name = forms.CharField(label="Nama pengirim", max_length=150, required=False)
    sender_bank = forms.CharField(label="Bank pengirim", max_length=50, required=False)
    transfer_date = forms.DateField(label="Tanggal transfer", required=False, widget=DateInput())
    destination_account = forms.ModelChoiceField(label="Rekening tujuan", required=False,
                                                 queryset=BankAccount.objects.filter(is_active=True))
    proof = forms.FileField(label="Bukti (opsional)", required=False,
                            widget=forms.ClearableFileInput(attrs={"accept": ACCEPT_ATTR}))
    verify_now = forms.BooleanField(label="Langsung tandai diterima", required=False, initial=True)

    def clean_proof(self):
        proof = self.cleaned_data.get("proof")
        return process_private_upload(proof, name="bukti") if proof else None


class LineEditForm(StyledFormMixin, forms.Form):
    quantity = forms.IntegerField(label="Jumlah tiket", min_value=1)
    primary = forms.TypedChoiceField(label="Kategori utama", coerce=int)
    backup1 = forms.TypedChoiceField(label="Cadangan 1", coerce=int, required=False, empty_value=None)
    backup2 = forms.TypedChoiceField(label="Cadangan 2", coerce=int, required=False, empty_value=None)

    def __init__(self, *args, line, **kwargs):
        initial = {"quantity": line.quantity, "primary": line.cat_primary_id,
                   "backup1": line.cat_backup1_id, "backup2": line.cat_backup2_id}
        super().__init__(*args, initial=initial, prefix=f"line{line.pk}", **kwargs)
        cats = [("", "—")] + [(c.pk, f"{c.name} ({c.get_fee_tier_display()})")
                              for c in line.order.event.categories.filter(is_active=True)]
        for name in ("primary", "backup1", "backup2"):
            self.fields[name].choices = cats


class NoteForm(StyledFormMixin, forms.Form):
    note = forms.CharField(label="Catatan internal", required=False, widget=forms.Textarea(attrs={"rows": 3}))


# ---------------------------------------------------------------------------
# Daftar
# ---------------------------------------------------------------------------

def _search(qs, q):
    q = q.strip()
    digits = digits_only(q)
    if len(digits) == 16 and len(q.replace(" ", "")) <= 19:  # NIK lengkap → cari lewat hash
        return qs.filter(lines__holder_nik_hash=nik_hash(digits)).distinct()
    if re.fullmatch(r"(?i)(drm-?)?[a-z0-9]{6}", q):
        qs_code = qs.filter(code=codes.normalize_code(q))
        if qs_code.exists():
            return qs_code
    cond = Q(code__icontains=q) | Q(buyer_name__icontains=q) | Q(buyer_email__icontains=q) | \
        Q(lines__holder_name__icontains=q)
    if len(digits) >= 6:
        cond |= Q(buyer_whatsapp__contains=digits.lstrip("0")) | Q(lines__holder_whatsapp__contains=digits.lstrip("0"))
    return qs.filter(cond).distinct()


@admin_required
def order_list(request):
    form = OrderFilterForm(request.GET or None)
    qs = Order.objects.select_related("event", "phase").prefetch_related("lines__slots", "payments")
    if form.is_valid():
        d = form.cleaned_data
        if d["q"]:
            qs = _search(qs, d["q"])
        if d["event"]:
            qs = qs.filter(event=d["event"])
        if d["phase"]:
            qs = qs.filter(phase=d["phase"])
        if d["status"]:
            qs = qs.filter(status__in=d["status"])
        if d["service"]:
            qs = qs.filter(lines__service_type=d["service"]).distinct()
        if d["method"]:
            qs = qs.filter(ticket_payment_method=d["method"])
        if d["late"]:
            qs = qs.filter(is_late_pelunasan=True)
        if d["dup"]:
            qs = qs.filter(has_duplicate_nik_warning=True)
    page = Paginator(qs.order_by("-created_at", "-id"), PAGE_SIZE).get_page(request.GET.get("page"))
    rows = []
    for order in page:
        lines = list(order.lines.all())
        rows.append({
            "order": order, "summary": settlement.summarize(order),
            "tickets": sum(ln.quantity for ln in lines),
            "services": sorted({ln.service_type for ln in lines}),
        })
    query = request.GET.copy()
    query.pop("page", None)
    return dash_render(request, "dashboard/orders/list.html", {
        "form": form, "page": page, "rows": rows, "query": query.urlencode(),
        "filtered": bool(request.GET),
    }, active="orders")


# ---------------------------------------------------------------------------
# Detail
# ---------------------------------------------------------------------------

def _get(code) -> Order:
    return get_object_or_404(order_detail_qs(), code=codes.normalize_code(code))


@admin_required
def order_detail(request, code, *, payment_form=None, note_form=None, line_forms=None):
    order = _get(code)
    summary = settlement.summarize(order)
    owner = is_owner(request.user)
    pre_war = order.status in PRE_WAR_STATUSES
    recalc = transitions.recalculate_preview(order) if order.status in transitions.RECALC_STATUSES else None
    late = (order.status == OrderStatus.MENUNGGU_PELUNASAN and order.phase.pelunasan_deadline
            and order.phase.pelunasan_deadline < timezone.now())
    lines = list(order.lines.all())
    if line_forms is None:
        line_forms = {ln.pk: LineEditForm(line=ln) for ln in lines} if order.status in transitions.RECALC_STATUSES else {}
    payments = list(order.payments.all())
    due = guidance.payment_due(order, summary)
    if payment_form is None and due:  # pembayaran manual hanya bila memang ada tagihan
        payment_form = ManualPaymentForm(initial={"amount": due.amount, "transfer_date": timezone.localdate(),
                                                  "sender_name": order.buyer_name})
    return dash_render(request, "dashboard/orders/detail.html", {
        "order": order, "summary": summary, "action": guidance.next_action(order, summary),
        "due": due, "lines": lines,
        "line_rows": [(ln, line_forms.get(ln.pk)) for ln in lines],
        "payments": payments, "timeline": list(order.timeline.all()),
        "audit": AuditLog.objects.filter(object_type="orders.order", object_id=str(order.pk))[:30],
        "tracking_url": tracking_url(order), "is_owner": owner, "pre_war": pre_war,
        "can_promote": order.status == OrderStatus.WAITING_LIST,
        "can_release": bool(late),
        "release_preview": settlement.cancellation_preview(order, CancelReason.LEWAT_BATAS_PELUNASAN) if late else None,
        "can_cancel": order.status not in (OrderStatus.SELESAI, OrderStatus.DIBATALKAN)
        and (owner or order.status == OrderStatus.WAITING_LIST),
        "cancel_preview": settlement.cancellation_preview(order, CancelReason.BATAL_ADMIN),
        "recalc": recalc,
        "payment_form": payment_form,
        "note_form": note_form or NoteForm(initial={"note": order.admin_note}),
        "pending_count": sum(1 for p in payments if p.status == PaymentStatus.MENUNGGU),
    }, active="orders")


def _back(request, order):
    target = request.POST.get("next") or ""
    if target and url_has_allowed_host_and_scheme(target, {request.get_host()}) and target.startswith("/kelola/"):
        return redirect(target)
    return redirect("dashboard:order_detail", code=order.code)


@admin_required
@require_POST
def order_action(request, code, action):
    order = get_object_or_404(Order, code=codes.normalize_code(code))
    actor = actor_for(request)
    try:
        if action == "naikkan":
            transitions.promote_from_waitlist(order, actor=actor)
            messages.success(request, f"{order.code} naik dari waiting list. Kabar WA disiapkan.")
        elif action == "lepas-slot":
            transitions.release_slot(order, actor=actor)
            messages.success(request, f"Slot {order.code} dilepas.")
        elif action == "batal":
            if not (is_owner(request.user) or order.status == OrderStatus.WAITING_LIST):
                raise PermissionDenied("Hanya Owner yang bisa membatalkan pesanan.")
            transitions.cancel_by_admin(order, actor=actor, note=request.POST.get("note", "").strip())
            messages.success(request, f"{order.code} dibatalkan.")
        elif action == "hitung-ulang":
            preview = transitions.recalculate_order(order, actor=actor)
            messages.success(request, "Tagihan dihitung ulang." if preview.changed else "Tagihan tidak berubah.")
        elif action == "catatan":
            form = NoteForm(request.POST)
            if form.is_valid():
                updates.save_admin_note(order, form.cleaned_data["note"], actor=actor)
                messages.success(request, "Catatan disimpan.")
        elif action == "bayar":
            form = ManualPaymentForm(request.POST, request.FILES)
            if not form.is_valid():
                return order_detail(request, order.code, payment_form=form)
            d = form.cleaned_data
            payment = transitions.submit_payment(order, amount=d["amount"], actor=actor, sender_name=d["sender_name"],
                                                 sender_bank=d["sender_bank"], transfer_date=d["transfer_date"],
                                                 proof=d["proof"], destination_account=d["destination_account"])
            if d["verify_now"]:
                transitions.verify_payment(payment, actor=actor)
            messages.success(request, "Pembayaran manual dicatat.")
        else:
            raise PermissionDenied
    except (InvalidTransition, ValidationError) as exc:
        messages.error(request, "; ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc))
    return _back(request, order)


@admin_required
@require_POST
def line_update(request, code, line_id):
    order = _get(code)
    line = get_object_or_404(OrderLine.objects.select_related("order__event"), pk=line_id, order=order)
    form = LineEditForm(request.POST, line=line)
    if form.is_valid():
        d = form.cleaned_data
        try:
            transitions.admin_update_line(line, actor=actor_for(request), quantity=d["quantity"], primary=d["primary"],
                                          backup1=d["backup1"], backup2=d["backup2"])
        except InvalidTransition as exc:
            messages.error(request, str(exc))
        except ValidationError as exc:
            for field, errors in exc.message_dict.items():
                for e in errors:
                    form.add_error(field if field in form.fields else None, e)
            return order_detail(request, order.code, line_forms={line.pk: form})
        else:
            messages.success(request, f"Baris #{line.sort_order + 1} diubah & tagihan dihitung ulang.")
            return redirect("dashboard:order_detail", code=order.code)
    return order_detail(request, order.code, line_forms={line.pk: form})


@admin_required
def holder_edit(request, code, line_id):
    order = _get(code)
    line = get_object_or_404(OrderLine.objects.select_related("order__phase"), pk=line_id, order=order)
    after_war = order.status not in PRE_WAR_STATUSES
    if after_war and not is_owner(request.user):
        raise PermissionDenied("Setelah war, hanya Owner yang bisa mengoreksi data pemegang.")
    initial = {"name": line.holder_name, "whatsapp": line.holder_whatsapp, "gender": line.holder_gender,
               "birth_date": line.holder_birth_date, "email": line.holder_email,
               "instagram": line.holder_instagram, "membership_no": line.holder_membership_no}
    form = HolderEditForm(request.POST or None, initial=initial, line=line, after_war=after_war)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        data = HolderData(name=d["name"], whatsapp=d["whatsapp"], nik=d.get("nik", ""), gender=d.get("gender", ""),
                          birth_date=d.get("birth_date"), email=d.get("email", ""),
                          instagram=d.get("instagram", ""), membership_no=d.get("membership_no", ""))
        try:
            updates.update_holder(line, data, actor=actor_for(request), reason=d.get("reason", ""))
        except (InvalidTransition, ValidationError) as exc:
            if isinstance(exc, ValidationError):
                for field, errors in exc.message_dict.items():
                    name = field.replace("holder_", "")
                    for e in errors:
                        form.add_error(name if name in form.fields else None, e)
            else:
                form.add_error(None, str(exc))
        else:
            messages.success(request, "Data pemegang tersimpan.")
            return redirect("dashboard:order_detail", code=order.code)
    return dash_render(request, "dashboard/orders/holder_edit.html",
                       {"order": order, "line": line, "form": form, "after_war": after_war}, active="orders")


@admin_required
@require_POST
def reveal_nik(request, code, line_id):
    """"Lihat NIK" — Owner saja, tercatat `nik.reveal` (docs/09 §2)."""
    if not request.user.has_perm("orders.view_full_nik") and not is_owner(request.user):
        raise PermissionDenied("Hanya Owner yang bisa melihat NIK penuh.")
    line = get_object_or_404(OrderLine.objects.select_related("order"), pk=line_id, order__code=codes.normalize_code(code))
    audit.log("nik.reveal", actor=actor_for(request), obj=line.order,
              summary=f"{line.order.code}: NIK pemegang #{line.sort_order + 1} dilihat")
    OrderTimeline.objects.create(order=line.order, title=f"NIK pemegang #{line.sort_order + 1} dilihat",
                                 message=request.user.get_username(), is_public=False,
                                 created_by_label=request.user.get_username())
    nik = line.holder_nik or "-"
    pretty = " ".join(nik[i:i + 4] for i in range(0, len(nik), 4)) if nik != "-" else nik
    response = HttpResponse(f'<span class="nik-full num">{pretty}</span>')
    response["Cache-Control"] = "no-store"
    return response
