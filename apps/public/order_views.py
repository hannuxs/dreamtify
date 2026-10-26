"""
Halaman customer: detail event, form pesanan, ringkasan biaya live, halaman sukses
(docs/04 §2–4). Semua angka dari `orders.services.pricing` — tidak ada rumus di JS.
"""
import secrets

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core import ratelimit
from apps.core.actors import Actor
from apps.core.enums import (
    FeeTier,
    OrderStatus,
    ServiceType,
    TicketPaymentMethod,
)
from apps.core.models import BankAccount
from apps.dashboard.permissions import is_admin
from apps.events import services as event_services
from apps.events.models import Event
from apps.orders.models import Order
from apps.orders.selectors import get_order
from apps.orders.services import quota, settlement, transitions
from apps.orders.services.links import check_tracking_token, tracking_path, tracking_url
from apps.orders.services.pricing import LineInput, PricingContext, PricingError, quote_order
from apps.orders.services.validation import BuyerData, HolderData, LineData

from .forms import AgreeForm, BuyerForm, LineForm, PaymentForm

ORDER_LIMIT = 5
ORDER_WINDOW = 10 * 60
SESSION_TOKENS = "order_form_tokens"
SESSION_TOKEN_RESULTS = "order_form_results"
SESSION_MY_ORDERS = "my_orders"

STEP_OF_PREFIX = {"buyer": 1, "lines": 2, "pay": 3, "agree": 4}


# ---------------------------------------------------------------------------
# Detail event
# ---------------------------------------------------------------------------

def _load_event(slug, request):
    event = get_object_or_404(Event.objects.prefetch_related("phases__fee_rules", "categories"), slug=slug)
    preview = event.status not in event_services.PUBLIC_EVENT_STATUSES
    if preview and not is_admin(request.user):
        raise Http404
    return event, preview


def _pick_phase(event, request, phases):
    wanted = request.GET.get("tahap") or request.POST.get("phase")
    for phase in phases:
        if str(phase.pk) == str(wanted):
            return phase
    open_ = [p for p in phases if event_services.phase_accepts_orders(event, p)]
    return (open_ or phases or [None])[0]


def _fee_table(event, phase, categories) -> list[dict]:
    """[{service, hint, fees: [(label tier, nominal|None)]}] — hanya tier yang ada kategorinya."""
    tiers = [t for t in FeeTier.values if any(c.fee_tier == t for c in categories)]
    rules = {(r.service_type, r.fee_tier): r.fee_per_ticket for r in phase.fee_rules.all()} if phase else {}
    return [
        {"service": s, "hint": event_services.SERVICE_HINTS.get(s, ""),
         "fees": [(FeeTier(t).label, rules.get((s, t))) for t in tiers]}
        for s in event.enabled_services()
    ]


def event_detail(request, slug):
    event, preview = _load_event(slug, request)
    phases = list(event.phases.all()) if preview else event_services.visible_phases(event)
    phase = _pick_phase(event, request, phases)
    categories = [c for c in event.categories.all() if c.is_active]
    accepts = bool(phase) and event_services.phase_accepts_orders(event, phase)
    remaining = quota.remaining(phase) if phase else None
    return render(request, "public/event_detail.html", {
        "event": event, "preview": preview, "phases": phases, "phase": phase,
        "categories": categories, "fee_rows": _fee_table(event, phase, categories),
        "accepts": accepts, "remaining": remaining,
        "quota_full": accepts and remaining is not None and remaining <= 0,
        "now": timezone.now(),
    })


# ---------------------------------------------------------------------------
# Form pesanan
# ---------------------------------------------------------------------------

def _new_form_token(request) -> str:
    token = secrets.token_urlsafe(16)
    tokens = request.session.get(SESSION_TOKENS, [])[-9:] + [token]
    request.session[SESSION_TOKENS] = tokens
    return token


def _active_indexes(data, max_lines) -> list[int]:
    return [i for i in range(max_lines) if f"lines-{i}-service_type" in data]


def _form_kwargs(event, phase, categories):
    return {"event": event, "phase": phase, "categories": categories}


def _build_forms(request, event, phase, categories, data=None):
    max_lines = event.max_lines_per_order
    buyer = BuyerForm(data, prefix="buyer")
    pay = PaymentForm(data, prefix="pay", event=event)
    agree = AgreeForm(data, prefix="agree")
    active = _active_indexes(data, max_lines) if data is not None else [0]
    default_service = (event.enabled_services() or [ServiceType.JASWAR])[0]
    lines = []
    for i in range(max_lines):
        is_active = i in active
        form = LineForm(data if is_active else None, prefix=f"lines-{i}",
                        initial={"service_type": default_service, "quantity": 1},
                        **_form_kwargs(event, phase, categories))
        lines.append({"index": i, "form": form, "active": is_active,
                      "service": (form["service_type"].value() or default_service),
                      "quantity": form["quantity"].value() or 1})
    return buyer, pay, agree, lines


def _map_service_errors(exc: ValidationError, buyer, pay, lines, active) -> list[str]:
    """Kunci error service (mis. `lines.0.holder_nik`) → field form yang sesuai."""
    general = []
    for key, errors in exc.message_dict.items():
        if key.startswith("buyer_") and key[6:] in buyer.fields:
            for e in errors:
                buyer.add_error(key[6:], e)
        elif key.startswith("lines.") and key.count(".") == 2:
            _, n, field = key.split(".")
            form = lines[active[int(n)]]["form"]
            for e in errors:
                if field in form.fields:
                    form.add_error(field, e)
                else:
                    form.add_error(None, e)
        elif key == "payment_method":
            for e in errors:
                pay.add_error("payment_method", e)
        else:
            general.extend(errors)
    return general


def _first_error_step(buyer, pay, agree, lines, general) -> int:
    if buyer.errors or general:
        return 1
    if any(line["active"] and line["form"].errors for line in lines):
        return 2
    if pay.errors:
        return 3
    if agree.errors:
        return 4
    return 1


def order_form(request, slug):
    event, preview = _load_event(slug, request)
    if preview:
        raise Http404
    phases = event_services.open_phases(event)
    phase = _pick_phase(event, request, phases)
    if phase is None or not event_services.phase_accepts_orders(event, phase):
        messages.info(request, "Pemesanan untuk event ini sedang tidak dibuka.")
        return redirect("public:event_detail", slug=event.slug)
    categories = [c for c in event.categories.all() if c.is_active]
    general = []
    initial_step = 1
    restore_draft = True

    if request.method == "POST":
        restore_draft = False
        if request.POST.get("website"):  # honeypot: bot
            return redirect("public:event_detail", slug=event.slug)
        token = request.POST.get("form_token", "")
        done = request.session.get(SESSION_TOKEN_RESULTS, {})
        if token in done:  # kirim ganda → tampilkan pesanan yang sudah dibuat
            return redirect("public:order_success", code=done[token])
        if token not in request.session.get(SESSION_TOKENS, []):
            messages.warning(request, "Form kedaluwarsa. Silakan periksa lalu kirim ulang.")
            return redirect(request.get_full_path())

        buyer, pay, agree, lines = _build_forms(request, event, phase, categories, request.POST)
        active = [ln["index"] for ln in lines if ln["active"]]
        valid = all([buyer.is_valid(), pay.is_valid(), agree.is_valid()]
                    + [lines[i]["form"].is_valid() for i in active]) and bool(active)
        if not active:
            general.append("Tambahkan minimal satu tiket.")
        if valid:
            ip = ratelimit.client_ip(request)
            if not ratelimit.hit("order", ip, ORDER_LIMIT, ORDER_WINDOW):
                general.append("Terlalu banyak pesanan dari jaringan ini. Coba lagi 10 menit lagi, "
                               "atau hubungi admin lewat WhatsApp.")
            else:
                try:
                    order = transitions.create_order(
                        phase=phase,
                        buyer=BuyerData(name=buyer.cleaned_data["name"], whatsapp=buyer.cleaned_data["whatsapp"],
                                        email=buyer.cleaned_data["email"],
                                        instagram=buyer.cleaned_data["instagram"],
                                        referral=buyer.cleaned_data["referral"]),
                        lines=[_line_data(lines[i]["form"].cleaned_data) for i in active],
                        payment_method=pay.cleaned_data["payment_method"],
                        actor=Actor(label="customer (form pesanan)", ip=ip, kind="customer"),
                        source_ip=ip, user_agent=request.META.get("HTTP_USER_AGENT", ""),
                    )
                except ValidationError as exc:
                    general.extend(_map_service_errors(exc, buyer, pay, lines, active))
                else:
                    tokens = [t for t in request.session.get(SESSION_TOKENS, []) if t != token]
                    request.session[SESSION_TOKENS] = tokens
                    request.session[SESSION_TOKEN_RESULTS] = {**done, token: order.code}
                    request.session[SESSION_MY_ORDERS] = request.session.get(SESSION_MY_ORDERS, [])[-19:] + [order.code]
                    return redirect("public:order_success", code=order.code)
        initial_step = _first_error_step(buyer, pay, agree, lines, general)
    else:
        token = _new_form_token(request)
        buyer, pay, agree, lines = _build_forms(request, event, phase, categories)

    labels = dict(TicketPaymentMethod.choices)
    return render(request, "public/order_form.html", {
        "event": event, "phase": phase, "phases": phases, "categories": categories,
        "buyer": buyer, "pay": pay, "agree": agree, "lines": lines, "general_errors": general,
        "form_token": token, "initial_step": initial_step, "restore_draft": restore_draft,
        "service_hints": event_services.SERVICE_HINTS,
        "payment_options": [(m, labels.get(m, m), event_services.PAYMENT_METHOD_HINTS.get(m, ""))
                            for m in event.payment_methods],
        "steps": ["Data pemesan", "Tiket", "Pembayaran", "Cek & setuju"],
        "remaining": quota.remaining(phase),
    })


def _line_data(d) -> LineData:
    return LineData(
        service_type=d["service_type"], quantity=d["quantity"], primary=d["primary"],
        backup1=d.get("backup1"), backup2=d.get("backup2"),
        holder=HolderData(
            name=d["holder_name"], whatsapp=d["holder_whatsapp"], email=d.get("holder_email") or "",
            nik=d.get("holder_nik") or "", gender=d.get("holder_gender") or "",
            birth_date=d.get("holder_birth_date"), instagram=(d.get("holder_instagram") or "").lstrip("@"),
            membership_no=d.get("holder_membership_no") or "", same_as_buyer=bool(d.get("same_as_buyer")),
        ),
    )


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@require_POST
def order_quote(request, slug):
    """Ringkasan biaya live (HTMX). Data setengah jadi diabaikan dengan tenang."""
    event = get_object_or_404(Event.objects.prefetch_related("categories"), slug=slug)
    phase = event.phases.filter(pk=_int(request.POST.get("phase"))).prefetch_related("fee_rules").first()
    if phase is None:
        return HttpResponseBadRequest("Tahap tidak dikenal.")
    ctx = PricingContext.for_phase(phase)
    active_ids = {cid for cid, c in ctx.categories.items() if c.is_active}
    method = request.POST.get("pay-payment_method") or ""
    rows, inputs, error = [], [], ""
    for number, i in enumerate(_active_indexes(request.POST, event.max_lines_per_order), start=1):
        service = request.POST.get(f"lines-{i}-service_type")
        qty = max(1, min(_int(request.POST.get(f"lines-{i}-quantity")) or 1, event.max_tickets_per_holder))
        cats = tuple(c for c in (_int(request.POST.get(f"lines-{i}-{k}")) for k in ("primary", "backup1", "backup2"))
                     if c in active_ids)
        if service not in event.enabled_services() or not cats:
            rows.append({"number": number, "service": service or "-", "qty": qty, "pending": True})
            continue
        inputs.append(LineInput(service, qty, cats))
        rows.append({"number": number, "service": service, "qty": qty, "pending": False})
    quote = None
    try:
        quote = quote_order(ctx, inputs, method or TicketPaymentMethod.VA_BCA)
    except PricingError as exc:
        error = str(exc)
    if quote:
        priced = iter(quote.lines)
        for row in rows:
            if not row["pending"]:
                row["quote"] = next(priced)
    return render(request, "public/_order_summary.html", {
        "rows": rows, "quote": quote, "error": error, "method": method, "event": event, "phase": phase,
        "titip": method == TicketPaymentMethod.TITIP_BAYAR,
    })


# ---------------------------------------------------------------------------
# Halaman sukses
# ---------------------------------------------------------------------------

def order_success(request, code):
    token = request.GET.get("t", "")
    allowed = code in request.session.get(SESSION_MY_ORDERS, []) or (token and check_tracking_token(code, token))
    if not allowed:
        raise Http404
    try:
        order = get_order(code)
    except Order.DoesNotExist:
        raise Http404 from None
    summary = settlement.summarize(order)
    link = tracking_url(order)
    return render(request, "public/order_success.html", {
        "order": order, "summary": summary, "tracking_url": link, "tracking_path": tracking_path(order),
        "accounts": BankAccount.objects.filter(is_active=True),
        "titip": order.ticket_payment_method == TicketPaymentMethod.TITIP_BAYAR,
        "waiting": order.status == OrderStatus.WAITING_LIST,
        "awaiting_fee": order.status == OrderStatus.MENUNGGU_FEE,
        "wa_text": f"Link lacak pesanan Dreamtify {order.code}: {link}",
        "draft_key": f"dt-draft:{order.event.slug}:{order.phase_id}",
        "tickets": sum(line.quantity for line in order.lines.all()),
        "phase_war": order.phase.war_at,
    })
