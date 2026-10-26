"""Setiap baris tabel pembatalan docs/02 §4.4 (+ ASUMSI D2, D3c)."""
from datetime import timedelta

import pytest
from freezegun import freeze_time

from apps.core.enums import CancelReason, LatePelunasanPolicy, OrderStatus
from apps.orders.selectors import get_order
from apps.orders.services import settlement, transitions

from .factories import CUSTOMER, GAGAL_CUSTOMER, JASWAR, line, make_fanmeet, make_order, pay, set_results

pytestmark = pytest.mark.django_db
S = OrderStatus
R = CancelReason


def contoh1(fx):
    return make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))])


def hasil(order):
    order = get_order(order.code)
    s = settlement.summarize(order)
    return order.status, order.cancel_reason, s.final_due, s.balance


def test_lewat_batas_fee(fanmeet):
    order = contoh1(fanmeet)
    with freeze_time(order.fee_deadline + timedelta(seconds=1)):
        transitions.cancel_expired_fee(order)
    assert hasil(order) == (S.DIBATALKAN, R.LEWAT_BATAS_FEE, 0, 0)


def test_batal_customer_sebelum_ada_uang(fanmeet):
    order = contoh1(fanmeet)
    preview = settlement.cancellation_preview(get_order(order.code))
    assert (preview.status, preview.refund) == (S.DIBATALKAN, 0)
    transitions.cancel_by_customer(order, actor=CUSTOMER)
    assert hasil(order) == (S.DIBATALKAN, R.BATAL_CUSTOMER, 0, 0)


def test_batal_customer_setelah_fee_diterima(fanmeet, admin):
    order = contoh1(fanmeet)
    pay(order, 500_000, admin)
    preview = settlement.cancellation_preview(get_order(order.code))
    assert (preview.status, preview.final_due, preview.refund) == (S.HANGUS, 500_000, 0)
    transitions.cancel_by_customer(order, actor=CUSTOMER)
    assert hasil(order) == (S.HANGUS, R.BATAL_CUSTOMER, 500_000, 0)


def test_batal_customer_waiting_list(admin):
    fx = make_fanmeet(slot_quota=0)
    order = contoh1(fx)
    assert order.status == S.WAITING_LIST
    transitions.cancel_by_customer(order, actor=CUSTOMER)
    assert hasil(order) == (S.DIBATALKAN, R.BATAL_CUSTOMER, 0, 0)


def lewat_pelunasan(fx, admin):
    order = contoh1(fx)
    pay(order, 500_000, admin)
    assert order.status == S.MENUNGGU_PELUNASAN
    return order


def test_lepas_slot_kebijakan_hangus(admin):
    fx = make_fanmeet(late_pelunasan_policy=LatePelunasanPolicy.HANGUS)
    order = lewat_pelunasan(fx, admin)
    with pytest.raises(transitions.InvalidTransition):  # belum lewat batas
        transitions.release_slot(order, actor=admin)
    with freeze_time(fx.phase.pelunasan_deadline + timedelta(minutes=1)):
        transitions.release_slot(order, actor=admin)
    assert hasil(order) == (S.HANGUS, R.LEWAT_BATAS_PELUNASAN, 500_000, 0)


def test_lepas_slot_kebijakan_refund_kurangi_booking(admin):
    fx = make_fanmeet(late_pelunasan_policy=LatePelunasanPolicy.REFUND_KURANGI_BOOKING)
    order = lewat_pelunasan(fx, admin)
    with freeze_time(fx.phase.pelunasan_deadline + timedelta(minutes=1)):
        transitions.release_slot(order, actor=admin)
    # min(dibayar 500rb, 2 tiket × 50rb) = 100rb ditahan → refund 400rb
    assert hasil(order) == (S.DIBATALKAN, R.LEWAT_BATAS_PELUNASAN, 100_000, 400_000)


@pytest.mark.parametrize("reason", [R.BATAL_ADMIN, R.EVENT_BATAL])
def test_batal_admin_refund_penuh(fanmeet, admin, reason):
    order = contoh1(fanmeet)
    pay(order, 7_500_000, admin)
    transitions.start_war(fanmeet.phase, actor=admin)  # admin tetap bisa membatalkan saat war
    transitions.cancel_by_admin(order, actor=admin, reason=reason)
    assert hasil(order) == (S.DIBATALKAN, reason, 0, 7_500_000)


def test_event_batal_mengubah_hangus_menjadi_refund_penuh(fanmeet, admin):
    order = contoh1(fanmeet)
    pay(order, 500_000, admin)
    transitions.cancel_by_customer(order, actor=CUSTOMER)
    assert hasil(order)[0] == S.HANGUS
    transitions.cancel_by_admin(order, actor=admin, reason=R.EVENT_BATAL)
    assert hasil(order) == (S.DIBATALKAN, R.EVENT_BATAL, 0, 500_000)


def test_pesanan_hangus_dengan_sisa_uang_masuk_antrian_refund(fanmeet, admin):
    """Antrian refund berbasis SALDO > 0 apa pun statusnya (contoh 6)."""
    order = contoh1(fanmeet)
    pay(order, 7_500_000, admin)
    transitions.cancel_by_customer(order, actor=CUSTOMER)
    assert hasil(order)[3] == 7_000_000
    transitions.record_refund(order, amount=7_000_000, actor=admin)
    assert hasil(order) == (S.HANGUS, R.BATAL_CUSTOMER, 500_000, 0)


def test_selesai_tidak_bisa_dibatalkan_admin(admin):
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))], method="VA_BCA")
    pay(order, 200_000, admin)
    transitions.start_war(fx.phase, actor=admin)
    set_results(order, admin, (GAGAL_CUSTOMER, None))
    assert order.status == S.SELESAI
    with pytest.raises(transitions.InvalidTransition):
        transitions.cancel_by_admin(order, actor=admin)
