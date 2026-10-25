from datetime import timedelta

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.utils import timezone


def home(request):
    """Beranda sementara ("Segera hadir"); diganti beranda final di fase 11."""
    return render(request, "public/coming_soon.html")


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
