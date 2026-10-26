"""
Perubahan data pesanan yang tidak mengubah status (docs/02 §11):
data pemegang, rekening refund, catatan internal. Semua tercatat di AuditLog
(tanpa nilai NIK / nomor rekening).
"""
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

from apps.core import audit
from apps.core.actors import Actor
from apps.core.crypto import digits_only, mask_account, nik_hash
from apps.core.enums import PRE_WAR_STATUSES, PaymentKind, ServiceType
from apps.core.phone import normalize_wa

from ..models import Order, OrderLine, OrderTimeline
from .transitions import InvalidTransition, _flag_duplicate_nik
from .validation import HolderData

HOLDER_FIELDS = ("holder_name", "holder_whatsapp", "holder_email", "holder_gender", "holder_birth_date",
                 "holder_instagram", "holder_membership_no")


@transaction.atomic
def update_holder(line, data: HolderData, *, actor: Actor, reason: str = "") -> OrderLine:
    """Ubah data pemegang tiket. Customer & admin: sebelum war. Setelah war: hanya
    dipanggil untuk Owner (dicek di view) dengan alasan wajib."""
    order = Order.objects.select_for_update().select_related("phase").get(pk=line.order_id)
    line = OrderLine.objects.select_for_update().get(pk=line.pk)
    if order.status not in PRE_WAR_STATUSES:
        if not actor.is_staff:
            raise InvalidTransition("Data pemegang tidak bisa diubah sejak war dimulai.")
        if not reason.strip():
            raise ValidationError({"reason": ["Alasan koreksi wajib diisi."]})

    errors = {}
    name = (data.name or "").strip()
    if not name:
        errors["holder_name"] = ["Nama pemegang wajib diisi."]
    try:
        wa = normalize_wa(data.whatsapp)
    except ValidationError as exc:
        errors["holder_whatsapp"] = exc.messages
        wa = ""
    new_nik = digits_only(data.nik)
    jaswar = line.service_type == ServiceType.JASWAR
    if new_nik and len(new_nik) != 16:
        errors["holder_nik"] = ["No. KTP (NIK) harus 16 digit."]
    if jaswar:
        if data.gender not in ("L", "P"):
            errors["holder_gender"] = ["Pilih jenis kelamin."]
        if not data.birth_date:
            errors["holder_birth_date"] = ["Tanggal lahir wajib diisi."]
        if not (data.email or "").strip():
            errors["holder_email"] = ["Email wajib diisi."]
        else:
            try:
                validate_email(data.email.strip())
            except ValidationError:
                errors["holder_email"] = ["Format email tidak valid."]
        if not (data.instagram or "").strip():
            errors["holder_instagram"] = ["Username IG wajib diisi."]
        if order.phase.membership_required and not (data.membership_no or "").strip():
            errors["holder_membership_no"] = ["No. membership wajib untuk tahap ini."]
    if errors:
        raise ValidationError(errors)

    new_values = {
        "holder_name": name, "holder_whatsapp": wa,
        "holder_email": (data.email or "").strip().lower() if jaswar else line.holder_email,
        "holder_gender": data.gender if jaswar else line.holder_gender,
        "holder_birth_date": data.birth_date if jaswar else line.holder_birth_date,
        "holder_instagram": (data.instagram or "").strip().lstrip("@") if jaswar else line.holder_instagram,
        "holder_membership_no": (data.membership_no or "").strip() if jaswar else line.holder_membership_no,
    }
    changed = [f for f in HOLDER_FIELDS if getattr(line, f) != new_values[f]]
    for f in HOLDER_FIELDS:
        setattr(line, f, new_values[f])
    if new_nik and nik_hash(new_nik) != line.holder_nik_hash:
        line.holder_nik = new_nik
        line.holder_nik_hash = nik_hash(new_nik)
        line.holder_nik_last4 = new_nik[-4:]
        changed.append("holder_nik")
    if not changed:
        return line
    line.save()
    if "holder_nik" in changed:
        hashes = list(OrderLine.objects.filter(order=order).exclude(holder_nik_hash="")
                      .values_list("holder_nik_hash", flat=True))
        _flag_duplicate_nik(order, hashes)
    labels = ", ".join(c.replace("holder_", "") for c in changed)
    OrderTimeline.objects.create(order=order, title=f"Data pemegang #{line.sort_order + 1} diubah",
                                 message=f"Diubah oleh {actor.label}: {labels}. {reason}".strip(),
                                 is_public=False, created_by_label=actor.label)
    audit.log("order.holder_update", actor=actor, obj=order,
              summary=f"{order.code}: data pemegang #{line.sort_order + 1} diubah ({labels})",
              data={"line": line.pk, "fields": changed, "reason": reason})
    return line


@transaction.atomic
def set_refund_account(order, *, bank: str, number: str, holder: str, actor: Actor) -> Order:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if not actor.is_staff and order.payments.filter(kind=PaymentKind.REFUND).exists():
        raise InvalidTransition("Refund sudah mulai diproses. Hubungi admin untuk mengubah rekening.")
    digits = digits_only(number)
    errors = {}
    if not (bank or "").strip():
        errors["bank"] = ["Nama bank / e-wallet wajib diisi."]
    if not 6 <= len(digits) <= 20:
        errors["number"] = ["Nomor rekening 6–20 digit."]
    if not (holder or "").strip():
        errors["holder"] = ["Nama pemilik rekening wajib diisi."]
    if errors:
        raise ValidationError(errors)
    order.refund_bank_name = bank.strip()[:50]
    order.refund_account_number = digits
    order.refund_account_holder = holder.strip()[:120]
    order.save(update_fields=["refund_bank_name", "refund_account_number", "refund_account_holder", "updated_at"])
    OrderTimeline.objects.create(order=order, title="Rekening refund disimpan",
                                 message=f"{order.refund_bank_name} {mask_account(digits)}",
                                 created_by_label=actor.public_label)
    audit.log("order.refund_account", actor=actor, obj=order,
              summary=f"{order.code}: rekening refund {order.refund_bank_name} {mask_account(digits)}")
    return order


def save_admin_note(order, note: str, *, actor: Actor) -> Order:
    order.admin_note = (note or "").strip()
    order.save(update_fields=["admin_note", "updated_at"])
    audit.log("order.note", actor=actor, obj=order, summary=f"{order.code}: catatan internal diubah")
    return order
