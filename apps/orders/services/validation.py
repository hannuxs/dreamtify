"""
Data masukan pesanan & validasi aturan baris tiket (docs/02 §3).

Form (fase 04) melakukan validasi per field untuk pesan yang ramah; fungsi
di sini adalah penjaga terakhir di sisi service. Error dikumpulkan sebagai
`ValidationError({"field": [...]})` dengan kunci seperti `buyer_whatsapp`
atau `lines.0.holder_nik` agar mudah dipetakan ke form.
"""
from dataclasses import dataclass, field, replace
from datetime import date
from typing import Optional

from django.core.exceptions import ValidationError
from django.core.validators import validate_email

from apps.core.crypto import digits_only
from apps.core.enums import EventStatus, Gender, PhaseStatus, ServiceType
from apps.core.phone import normalize_wa


@dataclass(frozen=True)
class BuyerData:
    name: str
    whatsapp: str
    email: str
    instagram: str = ""
    referral: str = ""
    note: str = ""


@dataclass(frozen=True)
class HolderData:
    name: str
    whatsapp: str = ""
    email: str = ""
    nik: str = ""
    gender: str = ""
    birth_date: Optional[date] = None
    instagram: str = ""
    membership_no: str = ""
    same_as_buyer: bool = False


@dataclass(frozen=True)
class LineData:
    service_type: str
    quantity: int
    primary: int
    backup1: Optional[int] = None
    backup2: Optional[int] = None
    holder: HolderData = field(default_factory=lambda: HolderData(name=""))

    @property
    def category_ids(self) -> tuple:
        return tuple(c for c in (self.primary, self.backup1, self.backup2) if c)


class _Errors:
    def __init__(self):
        self.data: dict[str, list[str]] = {}

    def add(self, key: str, message: str):
        self.data.setdefault(key, []).append(message)

    def raise_if_any(self):
        if self.data:
            raise ValidationError(self.data)


def _clean_wa(value: str, key: str, errors: _Errors, required: bool) -> str:
    if not value:
        if required:
            errors.add(key, "Nomor WhatsApp wajib diisi.")
        return ""
    try:
        return normalize_wa(value)
    except ValidationError as exc:
        errors.add(key, exc.messages[0])
        return ""


def _clean_email(value: str, key: str, errors: _Errors, required: bool) -> str:
    value = (value or "").strip()
    if not value:
        if required:
            errors.add(key, "Email wajib diisi.")
        return ""
    try:
        validate_email(value)
    except ValidationError:
        errors.add(key, "Format email tidak valid.")
    return value.lower()


def validate_order(*, event, phase, buyer: BuyerData, lines: list, payment_method: str,
                   active_category_ids: set, now, enforce_schedule: bool = True):
    """Validasi & normalisasi. Mengembalikan (buyer, lines) yang sudah bersih."""
    errors = _Errors()

    # --- Event & tahap ---
    if phase.event_id != event.pk:
        errors.add("phase", "Tahap tidak sesuai dengan event.")
    if enforce_schedule:
        if event.status != EventStatus.TAMPIL or phase.status != PhaseStatus.BUKA:
            errors.add("phase", "Pemesanan untuk tahap ini sedang tidak dibuka.")
        elif phase.order_open_at and now < phase.order_open_at:
            errors.add("phase", "Pemesanan untuk tahap ini belum dibuka.")
        elif phase.order_close_at and now >= phase.order_close_at:
            errors.add("phase", "Pemesanan untuk tahap ini sudah ditutup.")
    if payment_method not in (event.payment_methods or []):
        errors.add("payment_method", "Metode pembayaran tiket tidak tersedia untuk event ini.")

    # --- Pemesan ---
    buyer_name = (buyer.name or "").strip()
    if not buyer_name:
        errors.add("buyer_name", "Nama lengkap wajib diisi.")
    buyer = replace(
        buyer,
        name=buyer_name,
        whatsapp=_clean_wa(buyer.whatsapp, "buyer_whatsapp", errors, required=True),
        email=_clean_email(buyer.email, "buyer_email", errors, required=True),
        instagram=(buyer.instagram or "").strip().lstrip("@"),
        referral=(buyer.referral or "").strip(),
        note=(buyer.note or "").strip(),
    )

    # --- Baris tiket ---
    if not lines:
        errors.add("lines", "Minimal satu tiket.")
    if len(lines) > event.max_lines_per_order:
        errors.add("lines", f"Maksimal {event.max_lines_per_order} baris tiket per pesanan.")

    clean_lines = []
    for i, line in enumerate(lines):
        p = f"lines.{i}."
        if line.service_type not in event.enabled_services():
            errors.add(p + "service_type", "Layanan tidak tersedia untuk event ini.")
        try:
            qty = int(line.quantity)
        except (TypeError, ValueError):
            qty = 0
        if not 1 <= qty <= event.max_tickets_per_holder:
            errors.add(p + "quantity", f"Jumlah tiket 1–{event.max_tickets_per_holder}.")

        cats = [line.primary, line.backup1, line.backup2]
        if not line.primary:
            errors.add(p + "primary", "Kategori utama wajib dipilih.")
        for n, cid in enumerate(cats[1:], start=1):
            if n <= event.required_backups and not cid:
                errors.add(p + f"backup{n}", f"Kategori cadangan {n} wajib dipilih.")
        chosen = [c for c in cats if c]
        if any(c not in active_category_ids for c in chosen):
            errors.add(p + "primary", "Kategori tidak tersedia.")
        if len(chosen) != len(set(chosen)):
            errors.add(p + "backup1", "Kategori utama, cadangan 1, dan cadangan 2 harus berbeda.")

        h = line.holder
        hp = p + "holder_"
        name = (h.name or "").strip()
        if not name:
            errors.add(hp + "name", "Nama pemegang tiket wajib diisi.")
        jaswar = line.service_type == ServiceType.JASWAR
        nik = digits_only(h.nik)
        if jaswar or nik:
            if len(nik) != 16:
                errors.add(hp + "nik", "No. KTP (NIK) harus 16 digit.")
        if jaswar:
            if h.gender not in Gender.values:
                errors.add(hp + "gender", "Pilih jenis kelamin.")
            if not h.birth_date:
                errors.add(hp + "birth_date", "Tanggal lahir wajib diisi.")
            elif h.birth_date >= now.date():
                errors.add(hp + "birth_date", "Tanggal lahir tidak valid.")
            if not (h.instagram or "").strip():
                errors.add(hp + "instagram", "Username IG wajib diisi.")
            if phase.membership_required and not (h.membership_no or "").strip():
                errors.add(hp + "membership_no", "No. membership wajib untuk tahap ini.")
        holder = replace(
            h,
            name=name,
            nik=nik,
            whatsapp=_clean_wa(h.whatsapp, hp + "whatsapp", errors, required=True),
            email=_clean_email(h.email, hp + "email", errors, required=jaswar),
            instagram=(h.instagram or "").strip().lstrip("@"),
            membership_no=(h.membership_no or "").strip(),
            gender=h.gender if h.gender in Gender.values else "",
        )
        clean_lines.append(replace(line, quantity=qty, holder=holder))

    errors.raise_if_any()
    return buyer, clean_lines
