"""Mesin status docs/02 §5 + verifikasi pembayaran §4.2 + batas waktu §7."""
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone
from freezegun import freeze_time

from apps.core.enums import CancelReason, OrderStatus, PhaseStatus, SlotResult
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.orders.models import OrderTimeline, Payment
from apps.orders.services import transitions
from apps.orders.services.transitions import InvalidTransition, SlotConflict

from .factories import (
    CUSTOMER,
    GAGAL,
    JASTIP,
    JASWAR,
    SECURED,
    VA_BCA,
    buyer,
    jastip_holder,
    jaswar_holder,
    line,
    make_fanmeet,
    make_order,
    pay,
    set_results,
    slots,
)

pytestmark = pytest.mark.django_db
S = OrderStatus


def contoh1(fx):
    return make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))])


def keys(order):
    return sorted(Notification.objects.filter(order=order).values_list("template_key", flat=True))


# --- Pembuatan pesanan ------------------------------------------------------

def test_create_order_menyimpan_baris_dan_slot(fanmeet):
    order = make_order(fanmeet, [
        line(fanmeet, JASWAR, 2),
        line(fanmeet, JASTIP, 1, ("CAT 3", "CAT 2", "CAT 1"), holder=jastip_holder()),
    ])
    assert order.status == S.MENUNGGU_FEE
    assert order.code.startswith("DRM-") and len(order.code) == 10
    assert [ln.quantity for ln in order.lines.all()] == [2, 1]
    assert len(slots(order)) == 3
    assert order.buyer_whatsapp == "6281234567890"
    assert order.fee_deadline is not None
    assert order.pricing_snapshot["fees"]["JASWAR:VIP"] == 250_000
    assert OrderTimeline.objects.filter(order=order).count() == 1
    assert AuditLog.objects.filter(action="order.create", object_id=str(order.pk)).exists()
    # PESANAN_DIBUAT hanya email → tidak masuk Kotak Kabar WA
    assert keys(order) == []


def test_fee_deadline_maks_dua_jam_sebelum_war():
    fx = make_fanmeet(war_in=timedelta(hours=10))
    order = contoh1(fx)
    assert order.fee_deadline == fx.phase.war_at - timedelta(hours=2)


@pytest.mark.parametrize("cats, field", [
    (("Duality Package", "Duality Package", "CAT 2"), "lines.0.backup1"),
    (("Duality Package", "CAT 1", None), "lines.0.backup2"),
])
def test_kategori_harus_berbeda_dan_cadangan_wajib(fanmeet, cats, field):
    with pytest.raises(ValidationError) as exc:
        make_order(fanmeet, [line(fanmeet, JASWAR, 1, cats)])
    assert field in exc.value.message_dict


def test_jaswar_wajib_data_lengkap_jastip_minimal(fanmeet):
    with pytest.raises(ValidationError) as exc:
        make_order(fanmeet, [line(fanmeet, JASWAR, 1, holder=jaswar_holder(nik="123", birth_date=None,
                                                                            instagram=""))])
    errors = exc.value.message_dict
    assert {"lines.0.holder_nik", "lines.0.holder_birth_date", "lines.0.holder_instagram"} <= set(errors)
    order = make_order(fanmeet, [line(fanmeet, JASTIP, 1, holder=jastip_holder())])
    assert order.lines.get().holder_nik == ""


def test_membership_wajib_bila_tahap_mewajibkan(fanmeet):
    fanmeet.phase.membership_required = True
    fanmeet.phase.save()
    with pytest.raises(ValidationError) as exc:
        make_order(fanmeet, [line(fanmeet, JASWAR, 1)])
    assert "lines.0.holder_membership_no" in exc.value.message_dict


def test_tahap_tutup_tidak_bisa_pesan(fanmeet):
    fanmeet.phase.status = PhaseStatus.TUTUP
    fanmeet.phase.save()
    with pytest.raises(ValidationError) as exc:
        make_order(fanmeet, [line(fanmeet, JASWAR, 1)])
    assert "phase" in exc.value.message_dict


def test_nik_ganda_ditandai_tidak_diblokir(fanmeet):
    a = make_order(fanmeet, [line(fanmeet, JASWAR, 1)])
    b = make_order(fanmeet, [line(fanmeet, JASWAR, 1)], buyer_data=buyer(name="Budi"))
    a.refresh_from_db()
    assert a.has_duplicate_nik_warning and b.has_duplicate_nik_warning
    c = make_order(fanmeet, [line(fanmeet, JASWAR, 1, holder=jaswar_holder(nik="3171019999999999"))])
    assert not c.has_duplicate_nik_warning


# --- Verifikasi pembayaran (§4.2) ---------------------------------------------

def test_verifikasi_kurang_lalu_pas(fanmeet, admin):
    order = contoh1(fanmeet)
    pay(order, 300_000, admin)
    assert order.status == S.MENUNGGU_FEE  # kurang 200rb
    pay(order, 200_000, admin)
    assert order.status == S.MENUNGGU_PELUNASAN
    assert keys(order) == ["FEE_DITERIMA", "TAGIHAN_PELUNASAN"]


def test_verifikasi_lebih_dari_fee_tapi_belum_lunas(fanmeet, admin):
    order = contoh1(fanmeet)
    pay(order, 600_000, admin)
    assert order.status == S.MENUNGGU_PELUNASAN


def test_bayar_sekaligus_langsung_siap_war(fanmeet, admin):
    order = contoh1(fanmeet)
    pay(order, 7_500_000, admin)
    assert order.status == S.SIAP_WAR
    assert keys(order) == ["SIAP_WAR"]


def test_nominal_diterima_berbeda_dari_klaim(fanmeet, admin):
    order = contoh1(fanmeet)
    pay(order, 500_000, admin, received=450_000)
    assert order.status == S.MENUNGGU_FEE


def test_va_lunas_fee_langsung_siap_war(fanmeet, admin):
    order = make_order(fanmeet, [line(fanmeet, JASWAR, 1)], method=VA_BCA)
    pay(order, 250_000, admin)
    assert order.status == S.SIAP_WAR


def test_upload_bukti_pindah_ke_verifikasi(fanmeet):
    order = contoh1(fanmeet)
    with pytest.raises(ValidationError):  # customer wajib upload bukti
        transitions.submit_payment(order, amount=500_000, actor=CUSTOMER)
    transitions.submit_payment(order, amount=500_000, actor=CUSTOMER, proof="private/x.jpg")
    order.refresh_from_db()
    assert order.status == S.VERIFIKASI_FEE


def test_dua_bukti_menunggu_tetap_verifikasi(fanmeet, admin):
    order = contoh1(fanmeet)
    p1 = transitions.submit_payment(order, amount=200_000, actor=admin)
    transitions.submit_payment(order, amount=300_000, actor=admin)
    transitions.verify_payment(p1, actor=admin)
    order.refresh_from_db()
    assert order.status == S.VERIFIKASI_FEE  # masih ada bukti lain yang dicek


def test_tolak_kembali_menunggu_dan_kabar(fanmeet, admin):
    order = contoh1(fanmeet)
    payment = transitions.submit_payment(order, amount=500_000, actor=admin)
    with pytest.raises(ValidationError):
        transitions.reject_payment(payment, reason="", actor=admin)
    transitions.reject_payment(payment, reason="Dana belum masuk", actor=admin)
    order.refresh_from_db()
    assert order.status == S.MENUNGGU_FEE
    assert keys(order) == ["BUKTI_DITOLAK"]
    assert "Dana belum masuk" in Notification.objects.get(order=order).rendered_text
    with pytest.raises(InvalidTransition):  # sudah diproses
        transitions.verify_payment(payment, actor=admin)


def test_tolak_dekat_batas_memperpanjang_batas_fee(fanmeet, admin):
    order = contoh1(fanmeet)
    payment = transitions.submit_payment(order, amount=500_000, actor=admin)
    later = order.fee_deadline - timedelta(minutes=30)
    with freeze_time(later):
        transitions.reject_payment(payment, reason="Bukti tidak terbaca", actor=admin)
    order.refresh_from_db()
    assert order.fee_deadline >= later + timedelta(hours=6) - timedelta(seconds=1)


def test_kabar_tidak_ganda(fanmeet, admin):
    order = contoh1(fanmeet)
    pay(order, 500_000, admin)
    from apps.notifications.services import enqueue
    assert enqueue(order, "FEE_DITERIMA") == []
    assert keys(order).count("FEE_DITERIMA") == 1


# --- Transisi tidak sah ------------------------------------------------------

def test_transisi_tidak_sah(fanmeet, admin):
    order = contoh1(fanmeet)
    with pytest.raises(InvalidTransition):
        transitions._change_status(order, S.SELESAI, actor=admin, title="x")
    pay(order, 7_500_000, admin)
    with pytest.raises(InvalidTransition):  # SIAP_WAR tidak menunggu pembayaran
        transitions.submit_payment(order, amount=1, actor=admin)
    with pytest.raises(InvalidTransition):  # bukan waiting list
        transitions.promote_from_waitlist(order, actor=admin)
    with pytest.raises(InvalidTransition):  # bukan menunggu pelunasan
        transitions.release_slot(order, actor=admin)
    transitions.start_war(fanmeet.phase, actor=admin)
    with pytest.raises(InvalidTransition):  # war sudah mulai
        transitions.start_war(fanmeet.phase, actor=admin)
    with pytest.raises(InvalidTransition):  # customer tidak bisa batal sejak war
        transitions.cancel_by_customer(order, actor=CUSTOMER)


def test_setiap_transisi_menulis_timeline_dan_audit(fanmeet, admin):
    order = contoh1(fanmeet)
    pay(order, 500_000, admin)
    statuses = list(OrderTimeline.objects.filter(order=order).exclude(status="").values_list("status", flat=True))
    assert statuses == [S.MENUNGGU_FEE, S.VERIFIKASI_FEE, S.MENUNGGU_PELUNASAN]
    changes = AuditLog.objects.filter(action="order.status", object_id=str(order.pk))
    assert [(a.data["from"], a.data["to"]) for a in changes.order_by("id")] == [
        (S.MENUNGGU_FEE, S.VERIFIKASI_FEE), (S.VERIFIKASI_FEE, S.MENUNGGU_PELUNASAN)]


# --- Waiting list & batas waktu ---------------------------------------------------

def test_waiting_list_dan_naik(admin):
    fx = make_fanmeet(slot_quota=2)
    a = make_order(fx, [line(fx, JASWAR, 2)])
    b = make_order(fx, [line(fx, JASWAR, 1, holder=jaswar_holder(nik="3171019999999999"))],
                   buyer_data=buyer(name="Budi"))
    assert (a.status, b.status) == (S.MENUNGGU_FEE, S.WAITING_LIST)
    assert b.fee_deadline is None
    with pytest.raises(transitions.QuotaFull):
        transitions.promote_from_waitlist(b, actor=admin)
    transitions.cancel_by_customer(a, actor=CUSTOMER)
    transitions.promote_from_waitlist(b, actor=admin)
    b.refresh_from_db()
    assert b.status == S.MENUNGGU_FEE and b.fee_deadline is not None
    assert keys(b) == ["WAITING_LIST_NAIK"]


def test_batal_otomatis_lewat_batas_fee_idempoten(fanmeet):
    order = contoh1(fanmeet)
    with freeze_time(order.fee_deadline - timedelta(minutes=1)):
        assert transitions.cancel_expired_fee(order) is False
    with freeze_time(order.fee_deadline + timedelta(minutes=1)):
        assert transitions.cancel_expired_fee(order) is True
        assert transitions.cancel_expired_fee(order) is False  # aman dijalankan ulang
    order.refresh_from_db()
    assert (order.status, order.cancel_reason) == (S.DIBATALKAN, CancelReason.LEWAT_BATAS_FEE)


def test_tidak_batal_otomatis_bila_ada_bukti_menunggu(fanmeet, admin):
    order = contoh1(fanmeet)
    p = transitions.submit_payment(order, amount=200_000, actor=admin)
    transitions.verify_payment(p, actor=admin)  # kurang → MENUNGGU_FEE, tapi sudah ada uang
    with freeze_time(timezone.now() + timedelta(days=2)):
        assert transitions.cancel_expired_fee(order) is False


# --- Mode War --------------------------------------------------------------------

def siap_war(fx, admin):
    order = contoh1(fx)
    pay(order, 7_500_000, admin)
    return order


def test_start_war_hanya_memindahkan_siap_war(fanmeet, admin):
    siap = siap_war(fanmeet, admin)
    belum = make_order(fanmeet, [line(fanmeet, JASWAR, 1, holder=jaswar_holder(nik="3171019999999999"))],
                       buyer_data=buyer(name="Budi"))
    result = transitions.start_war(fanmeet.phase, actor=admin)
    assert result.started == [siap.code] and result.not_ready == [belum.code]
    siap.refresh_from_db()
    belum.refresh_from_db()
    assert (siap.status, belum.status) == (S.PROSES_WAR, S.MENUNGGU_FEE)
    fanmeet.phase.refresh_from_db()
    assert fanmeet.phase.status == PhaseStatus.WAR


def test_kategori_di_luar_pilihan_ditolak_bila_fallback_mati(admin):
    fx = make_fanmeet(fallback_any_category=False)
    order = siap_war(fx, admin)
    transitions.start_war(fx.phase, actor=admin)
    with pytest.raises(ValidationError):
        transitions.set_slot_result(slots(order)[0], SECURED, actor=admin, category=fx.cat("CAT 3"))


def test_konflik_versi_antar_admin(fanmeet, admin):
    order = siap_war(fanmeet, admin)
    transitions.start_war(fanmeet.phase, actor=admin)
    slot = slots(order)[0]
    transitions.set_slot_result(slot, GAGAL, actor=admin, expected_version=0)
    with pytest.raises(SlotConflict):
        transitions.set_slot_result(slot, SECURED, actor=admin, category=fanmeet.cat("CAT 1"),
                                    expected_version=0)


def test_undo_hasil_kembali_proses_war(fanmeet, admin):
    order = siap_war(fanmeet, admin)
    transitions.start_war(fanmeet.phase, actor=admin)
    set_results(order, admin, (SECURED, "Duality Package"), (GAGAL, None))
    assert order.status == S.PENYELESAIAN
    assert "HASIL_SEBAGIAN" in keys(order)
    # Undo tiket kedua (ASUMSI D4) → PROSES_WAR, kabar hasil yang belum terkirim dibuang
    transitions.set_slot_result(slots(order)[1], SlotResult.MENUNGGU, actor=admin)
    order.refresh_from_db()
    assert order.status == S.PROSES_WAR
    assert "HASIL_SEBAGIAN" not in keys(order)
    # Diisi ulang → hasil baru
    transitions.set_slot_result(slots(order)[1], SECURED, actor=admin, category=fanmeet.cat("CAT 1"))
    order.refresh_from_db()
    assert order.status == S.PENYELESAIAN
    assert "HASIL_SECURED" in keys(order)


def test_finish_war_menolak_bila_masih_ada_tiket_kosong(fanmeet, admin):
    order = siap_war(fanmeet, admin)
    transitions.start_war(fanmeet.phase, actor=admin)
    transitions.set_slot_result(slots(order)[0], SECURED, actor=admin, category=fanmeet.cat("CAT 1"))
    with pytest.raises(InvalidTransition):
        transitions.finish_war(fanmeet.phase, actor=admin)
    assert transitions.finish_war(fanmeet.phase, actor=admin, mark_rest_failed=True) == 1
    order.refresh_from_db()
    assert [s.result for s in slots(order)] == [SECURED, GAGAL]
    assert order.status == S.PENYELESAIAN
    fanmeet.phase.refresh_from_db()
    assert fanmeet.phase.status == PhaseStatus.SELESAI
    with pytest.raises(InvalidTransition):  # setelah war selesai, hasil tidak bisa diubah di Mode War
        transitions.set_slot_result(slots(order)[1], SECURED, actor=admin, category=fanmeet.cat("CAT 1"))


def test_refund_tidak_boleh_melebihi_saldo(fanmeet, admin):
    order = siap_war(fanmeet, admin)
    transitions.start_war(fanmeet.phase, actor=admin)
    set_results(order, admin, (GAGAL, None), (GAGAL, None))
    with pytest.raises(ValidationError):
        transitions.record_refund(order, amount=7_400_001, actor=admin)
    assert Payment.objects.filter(order=order, kind="REFUND").count() == 0
