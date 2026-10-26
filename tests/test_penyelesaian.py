"""Pesanan otomatis SELESAI hanya bila semua syarat terpenuhi (docs/02 §5, §9)."""
import pytest
from django.core.exceptions import ValidationError

from apps.core.enums import FulfillmentStatus, HandoverMethod, OrderStatus
from apps.notifications.models import Notification
from apps.orders.services import transitions

from .factories import GAGAL, JASTIP, JASWAR, SECURED, VA_BCA, jastip_holder, line, make_order, pay, set_results, slots

pytestmark = pytest.mark.django_db
S = OrderStatus
F = FulfillmentStatus


def war(fx, admin, order, *results):
    transitions.start_war(fx.phase, actor=admin)
    set_results(order, admin, *results)


def test_jastip_baru_selesai_saat_diserahkan(fanmeet, admin):
    order = make_order(fanmeet, [line(fanmeet, JASTIP, 1, ("CAT 3", "CAT 2", "CAT 1"), holder=jastip_holder())],
                       method=VA_BCA)
    pay(order, 250_000, admin)
    war(fanmeet, admin, order, (SECURED, "CAT 3"))
    assert order.status == S.PENYELESAIAN  # saldo 0 tapi gelang belum diserahkan
    slot = slots(order)[0]

    transitions.set_fulfillment(slot, F.DITUKAR, actor=admin)
    with pytest.raises(ValidationError):  # metode wajib
        transitions.set_fulfillment(slot, F.SIAP_DISERAHKAN, actor=admin)
    transitions.set_fulfillment(slot, F.SIAP_DISERAHKAN, actor=admin, method=HandoverMethod.TITIK_TEMU,
                                detail="Sab, 10.00 di lobby GBK")
    assert Notification.objects.filter(order=order, template_key="GELANG_SIAP").exists()
    with pytest.raises(transitions.InvalidTransition):  # tidak boleh mundur
        transitions.set_fulfillment(slot, F.DITUKAR, actor=admin)
    order.refresh_from_db()
    assert order.status == S.PENYELESAIAN
    transitions.set_fulfillment(slot, F.DISERAHKAN, actor=admin, receiver_name="Rina")
    order.refresh_from_db()
    assert order.status == S.SELESAI
    assert Notification.objects.filter(order=order, template_key="SELESAI_MINTA_TESTIMONI").exists()


def test_jaswar_selesai_dengan_info_dikirim(fanmeet, admin):
    order = make_order(fanmeet, [line(fanmeet, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))], method=VA_BCA)
    pay(order, 200_000, admin)
    war(fanmeet, admin, order, (SECURED, "CAT 3"))
    assert order.status == S.PENYELESAIAN
    with pytest.raises(transitions.InvalidTransition):  # status JASTIP tidak berlaku untuk JASWAR
        transitions.set_fulfillment(slots(order)[0], F.DITUKAR, actor=admin)
    transitions.set_fulfillment(slots(order)[0], F.INFO_DIKIRIM, actor=admin, note="Tukar di booth A")
    order.refresh_from_db()
    assert order.status == S.SELESAI


def test_refund_bertahap_sampai_selesai(fanmeet, admin):
    order = make_order(fanmeet, [line(fanmeet, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))])
    pay(order, 7_500_000, admin)
    war(fanmeet, admin, order, (GAGAL, None), (GAGAL, None))
    assert order.status == S.PENYELESAIAN
    assert Notification.objects.filter(order=order, template_key="REFUND_ISI_REKENING").exists()
    transitions.record_refund(order, amount=4_000_000, actor=admin)
    order.refresh_from_db()
    assert order.status == S.PENYELESAIAN  # saldo masih 3,4jt
    transitions.record_refund(order, amount=3_400_000, actor=admin)
    order.refresh_from_db()
    assert order.status == S.SELESAI


def test_bukti_menunggu_menahan_selesai(fanmeet, admin):
    order = make_order(fanmeet, [line(fanmeet, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))])
    pay(order, 200_000, admin)
    pay(order, 2_500_000, admin)
    war(fanmeet, admin, order, (SECURED, "Duality Package"))  # kekurangan 1,05jt
    assert Notification.objects.filter(order=order, template_key="KEKURANGAN_BAYAR").exists()
    transitions.set_fulfillment(slots(order)[0], F.INFO_DIKIRIM, actor=admin)
    transitions.submit_payment(order, amount=1_050_000, actor=admin)  # belum diverifikasi
    order.refresh_from_db()
    assert order.status == S.PENYELESAIAN
    payment = order.payments.get(kind="KEKURANGAN")
    transitions.verify_payment(payment, actor=admin)
    order.refresh_from_db()
    assert order.status == S.SELESAI
