"""Fase 07: Mode War, hasil per tiket via HTMX, undo, konflik, VA, VA mandiri, halaman lacak saat war."""
import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from freezegun import freeze_time

from apps.core.enums import NotificationStatus, OrderStatus, PhaseStatus, SlotResult, VaSource, VaStatus
from apps.notifications.models import Notification
from apps.orders.models import TicketSlot, VaNotice
from apps.orders.services import transitions
from apps.orders.services import va as va_service
from apps.orders.services.links import make_tracking_token

from .factories import JASWAR, VA_BCA, buyer, jaswar_holder, line, make_fanmeet, make_order, pay, slots

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def setup_groups():
    call_command("seed_initial", verbosity=0)


@pytest.fixture
def war_client(client):
    user = User.objects.create_user("admin-war", password="rahasia-panjang-1", is_staff=True)
    user.groups.add(Group.objects.get(name="Admin"))
    client.force_login(user)
    return client


def siap(fx, admin, method="TITIP_BAYAR", n=1):
    order = make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"),
                                 holder=jaswar_holder(nik=f"31710123456789{n:02d}"))],
                       method=method, buyer_data=buyer(name=f"Pemesan {n}"))
    pay(order, 7_500_000 if method == "TITIP_BAYAR" else 500_000, admin)
    assert order.status == OrderStatus.SIAP_WAR
    return order


def post_slot(client, slot, pick, **extra):
    data = {"pick": pick, "version": slot.version, **extra}
    return client.post(f"/kelola/war/tiket/{slot.pk}/", data, HTTP_HX_REQUEST="true")


def test_mulai_war_dan_isi_hasil_satu_ketukan(war_client, admin):
    fx = make_fanmeet()
    order = siap(fx, admin)
    html = war_client.get(f"/kelola/war/{fx.phase.pk}/").content.decode()
    assert order.code in html and "Mulai war" in html
    war_client.post(f"/kelola/war/{fx.phase.pk}/mulai/")
    fx.phase.refresh_from_db()
    order.refresh_from_db()
    assert fx.phase.status == PhaseStatus.WAR and order.status == OrderStatus.PROSES_WAR

    s1, s2 = slots(order)
    response = post_slot(war_client, s1, "primary", ticket_reference="TKT-001")
    assert response.status_code == 200
    assert "Dapat Duality Package" in response.content.decode() and "dt:toast" in response["HX-Trigger"]
    assert 'data-until="' in response.content.decode()  # tombol undo aktif
    s1.refresh_from_db()
    assert (s1.result, s1.secured_category.name, s1.ticket_reference) == (SlotResult.SECURED, "Duality Package", "TKT-001")

    post_slot(war_client, s2, "other", other=fx.cat("CAT 3").pk)
    order.refresh_from_db()
    assert order.status == OrderStatus.PENYELESAIAN
    assert Notification.objects.filter(order=order, template_key="HASIL_SECURED").exists()


def test_mulai_war_membuang_kabar_pra_war_yang_belum_terkirim(admin, admin_user):
    from apps.notifications import services as notify

    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))])
    pay(order, 500_000, admin)  # fee dulu → FEE_DITERIMA + TAGIHAN_PELUNASAN
    pay(order, 7_000_000, admin)  # pelunasan → SIAP_WAR
    sent = Notification.objects.get(order=order, template_key="FEE_DITERIMA")
    notify.mark_sent(sent, user=admin_user)
    assert Notification.objects.filter(order=order, template_key="SIAP_WAR",
                                       status=NotificationStatus.PERLU_DIKIRIM).exists()
    transitions.start_war(fx.phase, actor=admin)
    keys = set(Notification.objects.filter(order=order).values_list("template_key", flat=True))
    assert "SIAP_WAR" not in keys and "TAGIHAN_PELUNASAN" not in keys
    assert "FEE_DITERIMA" in keys  # yang sudah terkirim tetap jadi riwayat


def test_undo_dan_konflik_versi(war_client, admin):
    fx = make_fanmeet()
    order = siap(fx, admin)
    war_client.post(f"/kelola/war/{fx.phase.pk}/mulai/")
    slot = slots(order)[0]
    post_slot(war_client, slot, "gagal")
    stale_version = slot.version  # admin lain masih memegang versi lama
    slot.refresh_from_db()
    assert slot.result == SlotResult.GAGAL
    response = war_client.post(f"/kelola/war/tiket/{slot.pk}/", {"pick": "primary", "version": stale_version},
                               HTTP_HX_REQUEST="true")
    assert "admin lain" in json.loads(response["HX-Trigger"])["dt:toast"]["message"]
    slot.refresh_from_db()
    assert slot.result == SlotResult.GAGAL  # tidak tertimpa
    post_slot(war_client, slot, "undo")
    slot.refresh_from_db()
    assert slot.result == SlotResult.MENUNGGU


def test_selesaikan_war(war_client, admin):
    fx = make_fanmeet()
    order = siap(fx, admin)
    war_client.post(f"/kelola/war/{fx.phase.pk}/mulai/")
    post_slot(war_client, slots(order)[0], "gagal_customer")
    war_client.post(f"/kelola/war/{fx.phase.pk}/selesai/")
    fx.phase.refresh_from_db()
    assert fx.phase.status == PhaseStatus.WAR  # masih ada tiket kosong
    war_client.post(f"/kelola/war/{fx.phase.pk}/selesai/", {"mark_rest": "1"})
    fx.phase.refresh_from_db()
    assert fx.phase.status == PhaseStatus.SELESAI
    assert [s.result for s in slots(order)] == [SlotResult.GAGAL_CUSTOMER, SlotResult.GAGAL]


def test_filter_mode_war(war_client, admin):
    fx = make_fanmeet()
    titip = siap(fx, admin, n=1)
    va = siap(fx, admin, method=VA_BCA, n=2)
    war_client.post(f"/kelola/war/{fx.phase.pk}/mulai/")
    html = war_client.get(f"/kelola/war/{fx.phase.pk}/?f=va").content.decode()
    assert va.code in html and titip.code not in html
    post_slot(war_client, slots(titip)[0], "gagal")
    post_slot(war_client, slots(titip)[1], "gagal")
    html = war_client.get(f"/kelola/war/{fx.phase.pk}/?f=belum").content.decode()
    assert va.code in html and titip.code not in html


# --- VA -------------------------------------------------------------------------------

def test_va_dikirim_tampil_di_lacak_lalu_diklaim_dan_lunas(war_client, admin):
    fx = make_fanmeet()
    order = siap(fx, admin, method=VA_BCA)
    war_client.post(f"/kelola/war/{fx.phase.pk}/mulai/")
    expires = (timezone.localtime() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    prefix = f"va{order.pk}"
    response = war_client.post(f"/kelola/war/pesanan/{order.code}/va/", {
        f"{prefix}-bank": "BCA", f"{prefix}-va_number": "8808 1234 5678 9012", f"{prefix}-amount": "7.000.000",
        f"{prefix}-expires_at": expires, f"{prefix}-slots": [s.pk for s in slots(order)]}, HTTP_HX_REQUEST="true")
    assert response.status_code == 200 and "Kirim WA" in response.content.decode()
    va = VaNotice.objects.get(order=order)
    assert (va.va_number, va.amount, va.slots.count()) == ("8808123456789012", 7_000_000, 2)
    note = Notification.objects.get(order=order, template_key="VA_DIKIRIM")
    assert "8808123456789012" in note.rendered_text and note.status == NotificationStatus.PERLU_DIKIRIM

    customer = Client()
    html = customer.get(f"/lacak/{order.code}/?t={make_tracking_token(order)}").content.decode()
    assert "8808123456789012" in html and "Sudah saya bayar" in html and 'hx-trigger="every 10s"' in html
    customer.post(f"/lacak/{order.code}/va/{va.pk}/klaim/")
    va.refresh_from_db()
    assert va.status == VaStatus.DIKLAIM_CUSTOMER
    assert "Customer bilang sudah bayar" in war_client.get(f"/kelola/war/{fx.phase.pk}/").content.decode()
    war_client.post(f"/kelola/war/va/{va.pk}/lunas/")
    va.refresh_from_db()
    assert va.status == VaStatus.LUNAS


def test_customer_hanya_melihat_va_miliknya(admin):
    fx = make_fanmeet()
    a = siap(fx, admin, method=VA_BCA, n=1)
    b = siap(fx, admin, method=VA_BCA, n=2)
    transitions.start_war(fx.phase, actor=admin)
    va_b = va_service.create_va_notice(b, bank="BCA", va_number="1111222233334444", amount=1, actor=admin)
    ca = Client()
    html = ca.get(f"/lacak/{a.code}/?t={make_tracking_token(a)}").content.decode()
    assert "1111222233334444" not in html
    assert ca.post(f"/lacak/{b.code}/va/{va_b.pk}/klaim/").status_code == 404
    assert ca.post(f"/lacak/{a.code}/va/{va_b.pk}/klaim/").status_code == 404


def test_va_mandiri_dari_customer_titip_bayar(war_client, admin):
    fx = make_fanmeet()
    order = siap(fx, admin)
    war_client.post(f"/kelola/war/{fx.phase.pk}/mulai/")
    customer = Client()
    url = f"/lacak/{order.code}/?t={make_tracking_token(order)}"
    assert "Kirim VA-mu" in customer.get(url).content.decode()
    customer.post(f"/lacak/{order.code}/va-mandiri/", {"bank": "Mandiri", "va_number": "89508123456",
                                                       "amount": "3.500.000"})
    va = VaNotice.objects.get(order=order)
    assert va.source == VaSource.CUSTOMER and va.status == VaStatus.AKTIF
    html = war_client.get(f"/kelola/war/{fx.phase.pk}/").content.decode()
    assert "VA dari customer" in html and "89508123456" in html
    war_client.post(f"/kelola/war/va/{va.pk}/lunas/")
    va.refresh_from_db()
    assert va.status == VaStatus.LUNAS
    assert "Sudah dibayar tim" in customer.get(f"/lacak/{order.code}/").content.decode()


def test_va_mandiri_ditolak_bila_dimatikan(admin):
    fx = make_fanmeet(customer_va_enabled=False)
    order = siap(fx, admin)
    transitions.start_war(fx.phase, actor=admin)
    with pytest.raises(transitions.InvalidTransition):
        va_service.create_va_notice(order, bank="BCA", va_number="123456789", amount=1, actor=admin,
                                    source=VaSource.CUSTOMER)


def test_va_kedaluwarsa_lewat_run_periodic(admin):
    fx = make_fanmeet()
    order = siap(fx, admin, method=VA_BCA)
    transitions.start_war(fx.phase, actor=admin)
    va = va_service.create_va_notice(order, bank="BCA", va_number="123456789", amount=1, actor=admin,
                                     expires_at=timezone.now() + timedelta(minutes=5))
    with freeze_time(timezone.now() + timedelta(minutes=10)):
        call_command("run_periodic", verbosity=0)
        call_command("run_periodic", verbosity=0)
    va.refresh_from_db()
    assert va.status == VaStatus.KEDALUWARSA


def test_lacak_menampilkan_hasil_dan_saldo(admin):
    fx = make_fanmeet()
    order = siap(fx, admin)
    transitions.start_war(fx.phase, actor=admin)
    s1, s2 = slots(order)
    transitions.set_slot_result(s1, SlotResult.SECURED, actor=admin, category=fx.cat("Duality Package"))
    transitions.set_slot_result(s2, SlotResult.SECURED, actor=admin, category=fx.cat("CAT 1"))
    html = Client().get(f"/lacak/{order.code}/?t={make_tracking_token(order)}").content.decode()
    assert "Dapat Duality Package" in html and "Dapat CAT 1" in html
    assert "Rp 1.050.000" in html and "Isi rekening refund" in html  # contoh 1
    assert TicketSlot.objects.filter(line__order=order, result=SlotResult.SECURED).count() == 2
