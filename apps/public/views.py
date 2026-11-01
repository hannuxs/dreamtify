from datetime import timedelta

from django.conf import settings
from django.core.paginator import Paginator
from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone

from apps.core.enums import EventStatus, PhaseStatus
from apps.core.models import FaqItem, SiteSetting
from apps.events.models import Event
from apps.events.services import open_phases, visible_phases
from apps.orders.services import quota
from apps.testimonials import services as testimonial_services

TESTIMONIALS_PER_PAGE = 12


def home(request):
    cards = []
    for event in Event.objects.filter(status=EventStatus.TAMPIL).prefetch_related("phases"):
        phases = [p for p in visible_phases(event) if p.status != PhaseStatus.SELESAI]
        if not phases:
            continue
        open_ = open_phases(event)
        phase = (open_ or [p for p in phases if p.status == PhaseStatus.WAR] or phases)[0]
        cards.append({"event": event, "phase": phase, "open": bool(open_),
                      "remaining": quota.remaining(phase) if open_ else None})
    cards.sort(key=lambda c: not c["open"])  # yang sedang buka tampil lebih dulu
    return render(request, "public/home.html", {
        "cards": cards, "testimonials": testimonial_services.featured(),
        "faqs": FaqItem.objects.filter(is_active=True)[:5],
    })


def testimonials(request):
    event = Event.objects.filter(slug=request.GET.get("event", "")).first()
    qs = testimonial_services.published(event)
    summary = testimonial_services.rating_summary(qs)
    summary["rounded"] = round(summary["average"] or 0)
    events = Event.objects.filter(pk__in=testimonial_services.published().values("event")).order_by("name")
    return render(request, "public/testimonials.html", {
        "page": Paginator(qs, TESTIMONIALS_PER_PAGE).get_page(request.GET.get("halaman")),
        "event": event, "events": events, "summary": summary,
    })


def faq(request):
    return render(request, "public/faq.html", {"faqs": FaqItem.objects.filter(is_active=True)})


def terms(request):
    body = SiteSetting.load().general_terms
    return render(request, "public/legal.html", {"heading": "Syarat & ketentuan", "body": body})


def privacy(request):
    body = SiteSetting.load().privacy_policy
    return render(request, "public/legal.html", {"heading": "Kebijakan privasi", "body": body})


def robots(request):
    lines = ["User-agent: *", "Disallow: /kelola/", "Disallow: /lacak/", "Disallow: /p/", "Disallow: /berkas/",
             "Disallow: /pesanan/", f"Sitemap: {settings.SITE_URL}/sitemap.xml", ""]
    return HttpResponse("\n".join(lines), content_type="text/plain; charset=utf-8")


def sitemap(request):
    paths = ["/", "/testimoni/", "/faq/", "/syarat/", "/privasi/"]
    for slug in Event.objects.filter(status__in=(EventStatus.TAMPIL, EventStatus.SELESAI)).values_list("slug", flat=True):
        paths.append(reverse("public:event_detail", args=[slug]))
    return render(request, "public/sitemap.xml", {"urls": [settings.SITE_URL + p for p in paths]},
                  content_type="application/xml; charset=utf-8")


def _require_debug():
    if not settings.DEBUG:
        raise Http404


def component_gallery(request):
    """`/_komponen/` — galeri komponen untuk dicek visual. Hanya saat DEBUG."""
    _require_debug()
    now = timezone.now()
    context = {
        "swatches": [
            ("navy-900", "#052A45", "Teks utama, tombol utama"),
            ("navy-700", "#17476B", "Hover, judul sekunder"),
            ("sky-600", "#3E7FB0", "Link, ikon aktif"),
            ("sky-400", "#88B5D6", "Aksen, progress"),
            ("cloud-200", "#BCE2F5", "Kartu sorot, chip"),
            ("cloud-100", "#E4F3FC", "Latar bagian"),
            ("cloud-50", "#F5FBFF", "Latar halaman"),
            ("white", "#FFFFFF", "Kartu"),
            ("pink-400", "#F26877", "Aksen kecil, live"),
            ("pink-600", "#C23A4B", "Teks aksen pink"),
            ("pink-100", "#FDE4E7", "Latar badge pink"),
            ("sun-400", "#F5B83D", "Bintang rating"),
            ("ink-600", "#4A6175", "Teks sekunder"),
            ("line", "#D3E6F2", "Garis/border"),
            ("success", "#1E8E5A", ""),
            ("success-bg", "#E3F6EC", ""),
            ("warning", "#A15F00", ""),
            ("warning-bg", "#FFF1D1", ""),
            ("danger", "#C8333F", ""),
            ("danger-bg", "#FDE6E8", ""),
            ("info", "#2F6E9F", ""),
            ("info-bg", "#E4F3FC", ""),
        ],
        "status_badges": [
            ("neutral", "Masuk waiting list"),
            ("warning", "Menunggu pembayaran fee"),
            ("info", "Bukti fee sedang dicek"),
            ("warning", "Menunggu pelunasan tiket"),
            ("info", "Bukti pelunasan sedang dicek"),
            ("navy", "Siap war 🎫"),
            ("live", "War sedang berlangsung"),
            ("sky", "Hasil keluar — proses penyelesaian"),
            ("success", "Selesai ✨"),
            ("danger", "Dibatalkan"),
            ("danger", "Dibatalkan (fee hangus)"),
        ],
        "result_badges": [
            ("success", "Dapat CAT 1 🎉"),
            ("danger", "Tidak dapat"),
            ("danger", "Tidak dapat (VA tidak dibayar)"),
            ("neutral", "Menunggu war"),
        ],
        "icons": [
            "menu", "x", "copy", "check", "check-circle", "alert", "info", "chevron-down",
            "chevron-right", "arrow-right", "chat", "instagram", "mail", "home", "ticket",
            "list", "receipt", "bolt", "more", "clock", "calendar", "map-pin", "search",
            "settings", "users", "star", "upload", "download", "logout", "gift",
            "megaphone", "hourglass",
        ],
        "steps": ["Data pemesan", "Tiket", "Pembayaran", "Cek & setuju"],
        "countdown_far": now + timedelta(days=2, hours=3, minutes=14),
        "countdown_near": now + timedelta(minutes=42),
        "countdown_past": now - timedelta(minutes=5),
    }
    return render(request, "public/component_gallery.html", context)


def dashboard_preview(request):
    """`/_komponen/dashboard/` — pratinjau kerangka dashboard. Hanya saat DEBUG."""
    _require_debug()
    return render(request, "dashboard/preview.html")


def error_preview(request, code):
    """`/_komponen/404/` & `/_komponen/500/` — pratinjau halaman error. Hanya DEBUG."""
    _require_debug()
    return render(request, f"{code}.html", status=code)
