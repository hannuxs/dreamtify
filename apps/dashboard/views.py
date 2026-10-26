import json
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.db.models import Count, Q
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from apps.core import audit, ratelimit
from apps.core.actors import Actor
from apps.core.enums import (
    EventStatus,
    NotificationChannel,
    NotificationStatus,
    OrderStatus,
    PaymentStatus,
    PhaseStatus,
    TestimonialStatus,
)
from apps.core.models import AuditLog
from apps.events.models import Event, SalePhase
from apps.notifications.models import Notification
from apps.orders.models import Order, Payment
from apps.orders.services import quota
from apps.testimonials.models import Testimonial

from . import nav
from .forms import LoginForm
from .permissions import admin_required, is_admin, role_of

LOGIN_LIMIT = 5
LOGIN_WINDOW = 15 * 60
ADMIN_SESSION_SECONDS = 8 * 60 * 60


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def actor_for(request) -> Actor:
    return Actor.staff(request.user, ip=ratelimit.client_ip(request))


def is_htmx(request) -> bool:
    return request.headers.get("HX-Request") == "true"


def dash_render(request, template, context=None, *, active="", status=200, toast=None):
    ctx = {"nav": nav.build(request.user, active), "role": role_of(request.user)}
    ctx.update(context or {})
    response = render(request, template, ctx, status=status)
    if toast:
        # ensure_ascii: header HTTP harus ASCII
        response["HX-Trigger"] = json.dumps({"dt:toast": {"message": toast, "tone": "success"}})
    return response


def saved(request, message: str, url: str, rerender=None):
    """Setelah simpan: HTMX → render ulang panel + toast; biasa → PRG redirect."""
    if rerender is not None and is_htmx(request):
        return rerender(message)
    messages.success(request, message)
    return redirect(url)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

def login_view(request):
    if is_admin(request.user):
        return redirect("dashboard:home")
    ip = ratelimit.client_ip(request)
    form = LoginForm(request, data=request.POST or None)
    blocked = False
    error = ""
    if request.method == "POST":
        username = (request.POST.get("username") or "").strip().lower()
        ident = f"{ip}|{username}"
        if ratelimit.is_blocked("login", ident, LOGIN_LIMIT):
            # Jangan memanggil form.is_valid(): itu akan mencoba authenticate()
            blocked = True
            error = "Terlalu banyak percobaan gagal. Coba lagi 15 menit lagi."
            form = LoginForm(request, initial={"username": request.POST.get("username", "")})
        elif form.is_valid() and is_admin(form.get_user()):
            user = form.get_user()
            login(request, user)
            request.session.set_expiry(ADMIN_SESSION_SECONDS)
            ratelimit.reset("login", ident)
            audit.log("auth.login", actor=Actor.staff(user, ip=ip), summary=f"{user.get_username()} masuk")
            target = request.GET.get("next") or ""
            if not url_has_allowed_host_and_scheme(target, {request.get_host()}) or not target.startswith("/kelola/"):
                target = "/kelola/"
            return redirect(target)
        else:
            if form.is_valid():  # kredensial benar tapi bukan Owner/Admin
                error = "Akun ini tidak punya akses ke dashboard."
            ratelimit.hit("login", ident, LOGIN_LIMIT, LOGIN_WINDOW)
            audit.log("auth.login_failed", actor=Actor(label=username[:60] or "-", ip=ip),
                      summary=f"Login gagal untuk '{username[:60]}'")
    return render(request, "dashboard/login.html", {"form": form, "blocked": blocked, "error": error},
                  status=429 if blocked else 200)


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        audit.log("auth.logout", actor=actor_for(request), summary=f"{request.user.get_username()} keluar")
    logout(request)
    messages.info(request, "Kamu sudah keluar.")
    return redirect(settings.LOGIN_URL)


# ---------------------------------------------------------------------------
# Beranda tugas
# ---------------------------------------------------------------------------

@admin_required
def home(request):
    now = timezone.now()
    week = now + timedelta(days=7)
    stats = [
        {"label": "Bukti menunggu verifikasi", "value": Payment.objects.filter(status=PaymentStatus.MENUNGGU).count(),
         "url": reverse("dashboard:verify_queue")},
        {"label": "Lewat batas pelunasan", "value": Order.objects.filter(is_late_pelunasan=True).count(),
         "url": reverse("dashboard:waitlist")},
        {"label": "Waiting list", "value": Order.objects.filter(status=OrderStatus.WAITING_LIST).count(),
         "url": reverse("dashboard:waitlist")},
        {"label": "Kabar belum dikirim", "value": Notification.objects.filter(
            status=NotificationStatus.PERLU_DIKIRIM, channel=NotificationChannel.WA).count()},
        {"label": "Testimoni menunggu", "value": Testimonial.objects.filter(status=TestimonialStatus.MENUNGGU).count()},
    ]

    phases = (SalePhase.objects.select_related("event")
              .filter(event__status__in=(EventStatus.DRAFT, EventStatus.TAMPIL))
              .exclude(status=PhaseStatus.SELESAI)
              .annotate(**{f"n_{s.lower()}": Count("orders", filter=Q(orders__status=s)) for s in OrderStatus.values})
              .order_by("war_at", "event__name"))
    active = []
    for phase in phases:
        used = quota.used_tickets(phase)
        counts = [(OrderStatus(s).label, getattr(phase, f"n_{s.lower()}")) for s in OrderStatus.values]
        active.append({
            "phase": phase, "event": phase.event, "used": used,
            "percent": min(100, round(used * 100 / phase.slot_quota)) if phase.slot_quota else None,
            "counts": [c for c in counts if c[1]],
            "is_war": phase.status == PhaseStatus.WAR,
        })

    schedule = []
    for phase in SalePhase.objects.select_related("event").filter(
            Q(war_at__range=(now, week)) | Q(pelunasan_deadline__range=(now, week))):
        if phase.war_at and now <= phase.war_at <= week:
            schedule.append({"at": phase.war_at, "label": "War", "phase": phase})
        if phase.pelunasan_deadline and now <= phase.pelunasan_deadline <= week:
            schedule.append({"at": phase.pelunasan_deadline, "label": "Batas pelunasan", "phase": phase})
    schedule.sort(key=lambda s: s["at"])

    return dash_render(request, "dashboard/home.html", {
        "stats": stats, "active_phases": active, "schedule": schedule,
        "activity": AuditLog.objects.all()[:10],
        "has_events": Event.objects.exists(),
    }, active="home")


@admin_required
def menu(request):
    """"Lainnya" di bar bawah HP: semua menu."""
    return dash_render(request, "dashboard/menu.html", active="more")
