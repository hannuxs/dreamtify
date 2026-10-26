"""
Lacak pesanan (docs/04 §5) & berkas privat (docs/09 §4).
Semua perubahan lewat `orders.services` (transitions / updates).
"""
import mimetypes
from pathlib import Path

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core import ratelimit
from apps.core.actors import Actor
from apps.core.enums import (
    INCOMING_PAYMENT_KINDS,
    OrderStatus,
    PhaseStatus,
    TicketPaymentMethod,
    VaSource,
    PRE_WAR_STATUSES,
    CancelReason,
    PaymentKind,
    VaStatus,
)
from apps.core.models import BankAccount
from apps.core.phone import normalize_wa
from apps.dashboard.permissions import is_admin
from apps.orders.models import Order, OrderLine, Payment, TicketSlot, VaNotice
from apps.orders.selectors import get_order
from apps.orders.services import codes, guidance, settlement, transitions, updates, va as va_service
from apps.orders.services.links import check_promotor_file_signature, tracking_url
from apps.orders.services.transitions import InvalidTransition
from apps.orders.services.validation import HolderData

from . import access
from .forms import CustomerVaForm, HolderEditForm, PaymentUploadForm, RefundAccountForm, TrackLoginForm

LOGIN_LIMIT = 10
LOGIN_WINDOW = 15 * 60
UPLOAD_LIMIT = 10
UPLOAD_WINDOW = 60 * 60
GENERIC_FAIL = "Kode atau nomor WA tidak cocok. Periksa lagi, ya kak."


def _customer(request, order) -> Actor:
    if is_admin(request.user):
        return Actor.staff(request.user, ip=ratelimit.client_ip(request))
    return Actor.customer(order.code, ip=ratelimit.client_ip(request))


def _order_or_404(request, code) -> Order:
    code = codes.normalize_code(code)
    if not access.has_access(request, code):
        raise Http404  # sengaja 404 (bukan 403) agar tidak membocorkan keberadaan kode
    try:
        return get_order(code, public_timeline_only=True)
    except Order.DoesNotExist:
        raise Http404 from None


# ---------------------------------------------------------------------------
# Masuk lacak
# ---------------------------------------------------------------------------

def track_login(request):
    form = TrackLoginForm(request.POST or None)
    error = ""
    if request.method == "POST":
        ip = ratelimit.client_ip(request)
        if not ratelimit.hit("lacak", ip, LOGIN_LIMIT, LOGIN_WINDOW):
            error = "Terlalu banyak percobaan. Coba lagi 15 menit lagi, atau hubungi admin."
        elif form.is_valid():
            code = codes.normalize_code(form.cleaned_data["code"])
            try:
                wa = normalize_wa(form.cleaned_data["whatsapp"])
            except ValidationError:
                wa = None
            if wa and Order.objects.filter(code=code, buyer_whatsapp=wa).exists():
                access.grant(request, code)
                return redirect("public:track_order", code=code)
            error = GENERIC_FAIL
        else:
            error = GENERIC_FAIL
    return render(request, "public/track_login.html", {"form": form, "error": error},
                  status=429 if error.startswith("Terlalu") else 200)


# ---------------------------------------------------------------------------
# Halaman lacak
# ---------------------------------------------------------------------------

def _lacak_context(request, order, *, pay_form=None, refund_form=None, va_form=None):
    summary = settlement.summarize(order)
    due = guidance.payment_due(order, summary)
    accounts = list(BankAccount.objects.filter(is_active=True))
    if pay_form is None and due:
        pay_form = PaymentUploadForm(initial={
            "amount": due.amount, "transfer_date": timezone.localdate(), "sender_name": order.buyer_name})
    refund_needed = summary.refund_due > 0
    if refund_form is None and refund_needed:
        refund_form = RefundAccountForm(initial={"bank": order.refund_bank_name,
                                                 "holder": order.refund_account_holder or order.buyer_name})
    payments = list(order.payments.all())
    can_cancel = order.status in PRE_WAR_STATUSES
    return {
        "order": order, "summary": summary, "action": guidance.next_action(order, summary), "due": due,
        "due_covered": bool(due) and summary.pending_in >= due.amount,
        "accounts": accounts, "pay_form": pay_form, "refund_form": refund_form, "refund_needed": refund_needed,
        "refund_locked": any(p.kind == PaymentKind.REFUND for p in payments),
        "incoming": [p for p in payments if p.kind in INCOMING_PAYMENT_KINDS],
        "refunds": [p for p in payments if p.kind == PaymentKind.REFUND],
        "active_va": [v for v in order.va_notices.all()
                      if v.source == VaSource.ADMIN and v.status in (VaStatus.AKTIF, VaStatus.DIKLAIM_CUSTOMER)],
        "my_vas": [v for v in order.va_notices.all() if v.source == VaSource.CUSTOMER],
        "live_polling": order.phase.status == PhaseStatus.WAR,
        "va_form": va_form or (CustomerVaForm() if (
            order.event.customer_va_enabled and order.ticket_payment_method == TicketPaymentMethod.TITIP_BAYAR
            and order.phase.status == PhaseStatus.WAR and order.status == OrderStatus.PROSES_WAR) else None),
        "can_edit_holders": order.status in PRE_WAR_STATUSES,
        "can_cancel": can_cancel,
        "cancel_preview": settlement.cancellation_preview(order, CancelReason.BATAL_CUSTOMER) if can_cancel else None,
        "tracking_url": tracking_url(order),
        "wa_admin_text": f"Halo kak, saya mau tanya pesanan {order.code}",
    }


def track_order(request, code):
    order = _order_or_404(request, code)
    if not is_admin(request.user):
        Order.objects.filter(pk=order.pk).update(last_customer_view_at=timezone.now())
    return render(request, "public/track_order.html", _lacak_context(request, order))


@require_POST
def track_pay(request, code):
    order = _order_or_404(request, code)
    form = PaymentUploadForm(request.POST, request.FILES)
    if not ratelimit.hit("upload", order.code, UPLOAD_LIMIT, UPLOAD_WINDOW):
        form.add_error(None, "Terlalu banyak upload untuk pesanan ini. Coba lagi 1 jam lagi atau hubungi admin.")
    elif form.is_valid():
        d = form.cleaned_data
        try:
            transitions.submit_payment(order, amount=d["amount"], actor=_customer(request, order),
                                       sender_name=d["sender_name"], sender_bank=d["sender_bank"],
                                       transfer_date=d["transfer_date"], proof=d["proof"],
                                       destination_account=d["destination_account"])
        except InvalidTransition as exc:
            messages.error(request, str(exc))
            return redirect("public:track_order", code=order.code)
        except ValidationError as exc:
            for msg in exc.messages:
                form.add_error(None, msg)
        else:
            messages.success(request, "Bukti transfer terkirim! Kami cek dulu ya, kak.")
            return redirect("public:track_order", code=order.code)
    return render(request, "public/track_order.html", _lacak_context(request, order, pay_form=form))


@require_POST
def track_refund_account(request, code):
    order = _order_or_404(request, code)
    form = RefundAccountForm(request.POST)
    if form.is_valid():
        d = form.cleaned_data
        try:
            updates.set_refund_account(order, bank=d["bank"], number=d["number"], holder=d["holder"],
                                       actor=_customer(request, order))
        except InvalidTransition as exc:
            messages.error(request, str(exc))
            return redirect("public:track_order", code=order.code)
        except ValidationError as exc:
            for field, errors in exc.message_dict.items():
                for e in errors:
                    form.add_error(field if field in form.fields else None, e)
        else:
            messages.success(request, "Rekening refund tersimpan.")
            return redirect("public:track_order", code=order.code)
    return render(request, "public/track_order.html", _lacak_context(request, order, refund_form=form))


@require_POST
def track_cancel(request, code):
    order = _order_or_404(request, code)
    try:
        preview = transitions.cancel_by_customer(order, actor=_customer(request, order))
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    else:
        msg = "Pesanan dibatalkan."
        if preview.refund:
            msg += " Isi rekening refund agar dana bisa kami kembalikan."
        messages.success(request, msg)
    return redirect("public:track_order", code=order.code)


def track_holder_edit(request, code, line_id):
    order = _order_or_404(request, code)
    line = get_object_or_404(OrderLine.objects.select_related("order__phase"), pk=line_id, order=order)
    if order.status not in PRE_WAR_STATUSES:
        messages.error(request, "Data pemegang tidak bisa diubah sejak war dimulai. Hubungi admin bila ada kesalahan.")
        return redirect("public:track_order", code=order.code)
    initial = {"name": line.holder_name, "whatsapp": line.holder_whatsapp, "gender": line.holder_gender,
               "birth_date": line.holder_birth_date, "email": line.holder_email,
               "instagram": line.holder_instagram, "membership_no": line.holder_membership_no}
    form = HolderEditForm(request.POST or None, initial=initial, line=line)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        data = HolderData(name=d["name"], whatsapp=d["whatsapp"], nik=d.get("nik", ""), gender=d.get("gender", ""),
                          birth_date=d.get("birth_date"), email=d.get("email", ""),
                          instagram=d.get("instagram", ""), membership_no=d.get("membership_no", ""))
        try:
            updates.update_holder(line, data, actor=_customer(request, order))
        except InvalidTransition as exc:
            messages.error(request, str(exc))
            return redirect("public:track_order", code=order.code)
        except ValidationError as exc:
            for field, errors in exc.message_dict.items():
                name = field.replace("holder_", "")
                for e in errors:
                    form.add_error(name if name in form.fields else None, e)
        else:
            messages.success(request, "Data pemegang tersimpan.")
            return redirect("public:track_order", code=order.code)
    return render(request, "public/holder_edit.html", {"order": order, "line": line, "form": form})


# ---------------------------------------------------------------------------
# Berkas privat: /berkas/<jenis>/<id>/
# ---------------------------------------------------------------------------

FILE_KINDS = {
    # jenis: (model, field, ambil pesanan, select_related)
    "bukti": (Payment, "proof", lambda o: o.order, ("order__event",)),
    "etiket": (TicketSlot, "eticket_file", lambda o: o.line.order, ("line__order__event",)),
    "foto": (TicketSlot, "handover_photo", lambda o: o.line.order, ("line__order__event",)),
    "va": (VaNotice, "screenshot", lambda o: o.order, ("order__event",)),
}


def private_file(request, kind, pk):
    if kind not in FILE_KINDS:
        raise Http404
    model, field, owner, related = FILE_KINDS[kind]
    obj = get_object_or_404(model.objects.select_related(*related), pk=pk)
    stored = getattr(obj, field)
    if not stored:
        raise Http404
    order = owner(obj)
    allowed = (
        is_admin(request.user)
        or access.has_access(request, order.code)
        or (kind == "bukti" and check_promotor_file_signature(order.event, kind, pk, request.GET.get("s", "")))
    )
    if not allowed:
        raise Http404
    try:
        handle = stored.open("rb")
    except FileNotFoundError:
        raise Http404 from None
    ext = Path(stored.name).suffix.lower()
    response = FileResponse(handle, content_type=mimetypes.guess_type(stored.name)[0] or "application/octet-stream",
                            as_attachment=False, filename=f"{kind}-{order.code}{ext}")
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@require_POST
def track_va_claim(request, code, va_id):
    order = _order_or_404(request, code)
    notice = get_object_or_404(VaNotice, pk=va_id, order=order)
    try:
        va_service.claim_va_paid(notice, actor=_customer(request, order))
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Terima kasih! Kami cek pembayaran VA-nya ya, kak.")
    return redirect("public:track_order", code=order.code)


@require_POST
def track_va_mandiri(request, code):
    order = _order_or_404(request, code)
    form = CustomerVaForm(request.POST, request.FILES)
    if form.is_valid():
        d = form.cleaned_data
        try:
            va_service.create_va_notice(order, bank=d["bank"], va_number=d["va_number"], amount=d["amount"],
                                        expires_at=d["expires_at"], screenshot=d["screenshot"],
                                        source=VaSource.CUSTOMER, actor=_customer(request, order))
        except InvalidTransition as exc:
            messages.error(request, str(exc))
            return redirect("public:track_order", code=order.code)
        except ValidationError as exc:
            for field, errors in exc.message_dict.items():
                for e in errors:
                    form.add_error(field if field in form.fields else None, e)
        else:
            messages.success(request, "VA terkirim! Tim segera membayarkannya.")
            return redirect("public:track_order", code=order.code)
    return render(request, "public/track_order.html", _lacak_context(request, order, va_form=form))
