"""
Enam contoh WAJIB docs/02 §4.5 — angka harus persis.
Dijalankan lewat alur penuh: create_order → bayar → verifikasi → war → hasil.
"""
import pytest

from apps.core.enums import FulfillmentStatus, OrderStatus
from apps.orders.selectors import get_order
from apps.orders.services import settlement, transitions

from .factories import (
    GAGAL,
    GAGAL_CUSTOMER,
    JASTIP,
    JASWAR,
    SECURED,
    VA_BCA,
    jastip_holder,
    line,
    make_order,
    pay,
    set_results,
    slots,
)

pytestmark = pytest.mark.django_db


def summary(order):
    return settlement.summarize(get_order(order.code))


def contoh1_lunas(fx, admin):
    """Contoh 1 sampai SIAP_WAR: JASWAR q=2 Duality/CAT1/CAT2, titip bayar."""
    order = make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))])
    assert order.fee_due == 500_000
    assert order.pelunasan_due == 7_000_000
    pay(order, 500_000, admin)
    assert order.status == OrderStatus.MENUNGGU_PELUNASAN
    pay(order, 7_000_000, admin)
    assert order.status == OrderStatus.SIAP_WAR
    assert summary(order).paid_in == 7_500_000
    return order


def test_contoh1_sebagian_beda_kategori(fanmeet, admin):
    order = contoh1_lunas(fanmeet, admin)
    transitions.start_war(fanmeet.phase, actor=admin)
    set_results(order, admin, (SECURED, "Duality Package"), (SECURED, "CAT 1"))
    s = summary(order)
    assert s.final_due == 6_450_000  # (250rb + 200rb) + (3,5jt + 2,5jt)
    assert s.balance == 1_050_000  # refund
    assert order.status == OrderStatus.PENYELESAIAN


def test_contoh2_gagal_semua(fanmeet, admin):
    order = contoh1_lunas(fanmeet, admin)
    transitions.start_war(fanmeet.phase, actor=admin)
    set_results(order, admin, (GAGAL, None), (GAGAL, None))
    s = summary(order)
    assert s.final_due == 100_000  # 2 × booking slot 50rb
    assert s.balance == 7_400_000


def test_contoh3_va_kelalaian_customer(fanmeet, admin):
    order = make_order(fanmeet, [line(fanmeet, JASTIP, 1, ("CAT 3", "CAT 2", "CAT 1"))], method=VA_BCA)
    assert order.fee_due == 250_000
    assert order.pelunasan_due == 0
    pay(order, 250_000, admin)
    assert order.status == OrderStatus.SIAP_WAR  # VA: tidak ada pelunasan
    transitions.start_war(fanmeet.phase, actor=admin)
    set_results(order, admin, (GAGAL_CUSTOMER, None))
    s = summary(order)
    assert s.final_due == 250_000
    assert s.balance == 0  # tidak ada refund
    assert order.status == OrderStatus.SELESAI  # tidak ada saldo & penyerahan


def test_contoh4_dua_baris_beliin_teman(fanmeet, admin):
    order = make_order(fanmeet, [
        line(fanmeet, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2")),
        line(fanmeet, JASTIP, 1, ("CAT 3", "CAT 2", "CAT 1"), holder=jastip_holder("Teman Rina")),
    ])
    assert order.fee_due == 750_000  # 2×250rb + 1×250rb
    assert order.pelunasan_due == 9_500_000  # 2×3,5jt + 1×2,5jt (termahal di pilihan B = CAT 1)
    pay(order, 750_000, admin)
    pay(order, 9_500_000, admin)
    assert order.status == OrderStatus.SIAP_WAR
    transitions.start_war(fanmeet.phase, actor=admin)
    set_results(order, admin, (SECURED, "Duality Package"), (GAGAL, None), (SECURED, "CAT 3"))
    fee_final, price_final = settlement.war_totals(get_order(order.code))
    assert fee_final == 550_000  # 250rb + 50rb + 250rb
    assert price_final == 5_000_000  # 3,5jt + 0 + 1,5jt
    s = summary(order)
    assert s.final_due == 5_550_000
    assert s.balance == 4_700_000  # 10,25jt − 5,55jt


def test_contoh5_kategori_lebih_mahal(fanmeet, admin):
    order = make_order(fanmeet, [line(fanmeet, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))])
    assert order.fee_due == 200_000
    assert order.pelunasan_due == 2_500_000
    pay(order, 200_000, admin)
    pay(order, 2_500_000, admin)
    transitions.start_war(fanmeet.phase, actor=admin)
    # Semua pilihan habis → tim mengamankan Duality (di luar pilihan)
    set_results(order, admin, (SECURED, "Duality Package"))
    s = summary(order)
    assert s.final_due == 3_750_000  # 250rb (fee VIP) + 3,5jt
    assert s.balance == -1_050_000
    assert s.shortfall == 1_050_000  # kekurangan
    assert order.status == OrderStatus.PENYELESAIAN

    # Customer melunasi kekurangan → saldo 0; JASWAR selesai setelah info dikirim
    payment = transitions.submit_payment(order, amount=1_050_000, actor=admin)
    assert payment.kind == "KEKURANGAN"
    transitions.verify_payment(payment, actor=admin)
    assert summary(order).balance == 0
    order.refresh_from_db()
    assert order.status == OrderStatus.PENYELESAIAN
    transitions.set_fulfillment(slots(order)[0], FulfillmentStatus.INFO_DIKIRIM, actor=admin)
    order.refresh_from_db()
    assert order.status == OrderStatus.SELESAI


def test_contoh6_batal_setelah_lunas(fanmeet, admin):
    order = contoh1_lunas(fanmeet, admin)
    preview = settlement.cancellation_preview(get_order(order.code))
    assert (preview.status, preview.final_due, preview.refund) == (OrderStatus.HANGUS, 500_000, 7_000_000)
    transitions.cancel_by_customer(order, actor=admin)
    order.refresh_from_db()
    assert order.status == OrderStatus.HANGUS
    s = summary(order)
    assert s.final_due == 500_000
    assert s.balance == 7_000_000  # refund
