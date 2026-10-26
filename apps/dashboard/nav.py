"""Menu dashboard (docs/05 peta URL). Item tanpa `url_name` = belum dibangun ("segera")."""
from dataclasses import dataclass

from django.urls import reverse

from .permissions import is_owner


@dataclass(frozen=True)
class NavItem:
    key: str
    label: str
    icon: str
    url_name: str | None = None
    group: str = ""
    owner_only: bool = False
    short: str = ""  # label bar bawah HP


ITEMS = (
    NavItem("home", "Beranda tugas", "home", "dashboard:home", short="Beranda"),
    NavItem("events", "Event", "calendar", "dashboard:event_list", group="Operasional"),
    NavItem("orders", "Pesanan", "list", group="Operasional"),
    NavItem("verify", "Verifikasi", "check-circle", group="Operasional"),
    NavItem("waitlist", "Waiting list", "hourglass", group="Operasional"),
    NavItem("war", "Mode War", "bolt", group="Operasional", short="War"),
    NavItem("settlement", "Penyelesaian", "receipt", group="Operasional"),
    NavItem("handover", "Penyerahan", "gift", group="Operasional"),
    NavItem("inbox", "Kotak Kabar", "megaphone", group="Operasional"),
    NavItem("reports", "Rekap & Ekspor", "download", group="Operasional"),
    NavItem("testimonials", "Testimoni", "star", group="Operasional"),
    NavItem("settings", "Pengaturan", "settings", "dashboard:settings", group="Owner", owner_only=True),
    NavItem("users", "Pengguna", "users", "dashboard:user_list", group="Owner", owner_only=True),
    NavItem("log", "Log aktivitas", "list", "dashboard:audit_log", group="Owner", owner_only=True),
)

# Bar bawah HP: Beranda · Pesanan · Verifikasi · War · Lainnya
BOTTOM_KEYS = ("home", "orders", "verify", "war")


def build(user, active: str = "") -> dict:
    owner = is_owner(user)
    items = []
    for item in ITEMS:
        if item.owner_only and not owner:
            continue
        items.append({
            "key": item.key, "label": item.label, "short": item.short or item.label, "icon": item.icon, "group": item.group,
            "url": reverse(item.url_name) if item.url_name else None,
            "active": item.key == active,
        })
    bottom = [i for i in items if i["key"] in BOTTOM_KEYS]
    return {"items": items, "bottom": bottom, "more_active": active not in BOTTOM_KEYS}
