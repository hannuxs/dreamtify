"""Fase 06: daftar & detail pesanan, Lihat NIK, verifikasi, waiting list, hitung ulang, run_periodic."""
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from freezegun import freeze_time

from apps.core.enums import OrderStatus, PaymentStatus, PhaseStatus
from apps.core.models import AuditLog
from apps.orders.models import Order, Payment, TicketSlot
from apps.orders.services import transitions

from .factories import CUSTOMER, JASWAR, buyer, jaswar_holder, line, make_fanmeet, make_order, pay

pytestmark = pytest.mark.django_db
User = get_user_model()
NIK = "3171012345678901"


@pytest.fixture(autouse=True)
def groups():
    call_command("seed_initial", verbosity=0)


def login(client, username, role):
    user = User.objects.create_user(username, password="rahasia-panjang-1", is_staff=True)
    user.groups.add(Group.objects.get(name=role))
    client.force_login(user)
    return client


@pytest.fixture
def owner_client(client):
    return login(client, "owner1", "Owner")


@pytest.fixture
def admin_client(client):
    return login(client, "admin-dash", "Admin")


def contoh1(fx, n=0, **kw):
    return make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"),
                                holder=jaswar_holder(nik=f"31710123456789{n:02d}", name=f"Pemegang {n}"))],
                      buyer_data=buyer(name=f"Pemesan {n}", whatsapp=f"0812345678{n:02d}"), **kw)


# --- Daftar --------------------------------------------------------------------

def test_daftar_pesanan_tanpa_n_plus_1(admin_client, admin):
    fx = make_fanmeet()
    for n in range(2):
        pay(contoh1(fx, n), 500_000, admin)

    def count():
        with CaptureQueriesContext(connection) as ctx:
            assert admin_client.get("/kelola/pesanan/").status_code == 200
        return len(ctx.captured_queries)

    count()  # pemanasan: request pertama ikut menyimpan sesi
    few = count()
    for n in range(2, 8):
        pay(contoh1(fx, n), 500_000, admin)
    assert count() == few


def test_cari_kode_nama_wa_dan_nik_lengkap(admin_client):
    fx = make_fanmeet()
    a, b = contoh1(fx, 1), contoh1(fx, 2)
    for q, expected in ((a.code, a), (a.code[4:].lower(), a), ("Pemesan 2", b), ("Pemegang 1", a),
                        ("081234567802", b), ("3171 0123 4567 8901", a)):
        html = admin_client.get("/kelola/pesanan/", {"q": q}).content.decode()
        other = b if expected == a else a
        assert expected.code in html and other.code not in html, q


def test_filter_status(admin_client, admin):
    fx = make_fanmeet()
    a, b = contoh1(fx, 1), contoh1(fx, 2)
    pay(a, 500_000, admin)
    html = admin_client.get("/kelola/pesanan/", {"status": ["MENUNGGU_PELUNASAN"]}).content.decode()
    assert a.code in html and b.code not in html


# --- Detail & NIK ---------------------------------------------------------------------

def test_detail_nik_tersamar_dan_lihat_nik_hanya_owner(admin_client, client):
    fx = make_fanmeet()
    order = contoh1(fx, 1)
    ln = order.lines.get()
    html = admin_client.get(f"/kelola/pesanan/{order.code}/").content.decode()
    assert "3171012345678901" not in html and "•••• •••• •••• 8901" in html and "Lihat NIK" not in html
    assert admin_client.post(f"/kelola/pesanan/{order.code}/nik/{ln.pk}/").status_code == 403

    owner = login(client, "owner9", "Owner")
    assert "Lihat NIK" in owner.get(f"/kelola/pesanan/{order.code}/").content.decode()
    response = owner.post(f"/kelola/pesanan/{order.code}/nik/{ln.pk}/")
    assert response.status_code == 200 and "3171 0123 4567 8901" in response.content.decode()
    log = AuditLog.objects.get(action="nik.reveal")
    assert log.actor.username == "owner9" and "3171012345678901" not in log.summary


def test_pembayaran_manual_dan_catatan(admin_client):
    order = contoh1(make_fanmeet(), 1)
    admin_client.post(f"/kelola/pesanan/{order.code}/aksi/bayar/",
                      {"amount": "500.000", "sender_name": "Rina", "verify_now": "on"})
    order.refresh_from_db()
    assert order.status == OrderStatus.MENUNGGU_PELUNASAN
    assert Payment.objects.get(order=order).submitted_via == "ADMIN"
    admin_client.post(f"/kelola/pesanan/{order.code}/aksi/catatan/", {"note": "Customer minta dikabari via IG"})
    order.refresh_from_db()
    assert order.admin_note == "Customer minta dikabari via IG"


def test_admin_tidak_bisa_batalkan_pesanan_berbayar_owner_bisa(admin_client, client, admin):
    order = contoh1(make_fanmeet(), 1)
    pay(order, 500_000, admin)
    assert admin_client.post(f"/kelola/pesanan/{order.code}/aksi/batal/").status_code == 403
    owner = login(client, "owner9", "Owner")
    owner.post(f"/kelola/pesanan/{order.code}/aksi/batal/", {"note": "Duplikat pesanan"})
    order.refresh_from_db()
    assert (order.status, order.cancel_reason) == (OrderStatus.DIBATALKAN, "BATAL_ADMIN")


def test_hitung_ulang_tagihan_dan_ubah_baris(admin_client, admin):
    fx = make_fanmeet()
    order = contoh1(fx, 1)
    pay(order, 7_500_000, admin)
    assert order.status == OrderStatus.SIAP_WAR
    fx.cat("Duality Package").price = 4_000_000
    fx.cat("Duality Package").save()
    html = admin_client.get(f"/kelola/pesanan/{order.code}/").content.decode()
    assert "Hitung ulang tagihan" in html and "Rp 8.000.000" in html
    admin_client.post(f"/kelola/pesanan/{order.code}/aksi/hitung-ulang/")
    order.refresh_from_db()
    assert order.pelunasan_due == 8_000_000
    assert order.status == OrderStatus.MENUNGGU_PELUNASAN  # kurang 1 jt → kembali menunggu pelunasan
    assert AuditLog.objects.filter(action="order.recalculate").exists()

    ln = order.lines.get()
    prefix = f"line{ln.pk}"
    admin_client.post(f"/kelola/pesanan/{order.code}/baris/{ln.pk}/", {
        f"{prefix}-quantity": "3", f"{prefix}-primary": fx.cat("CAT 1").pk,
        f"{prefix}-backup1": fx.cat("CAT 2").pk, f"{prefix}-backup2": fx.cat("CAT 3").pk})
    order.refresh_from_db()
    assert TicketSlot.objects.filter(line__order=order).count() == 3
    assert order.fee_due == 3 * 200_000 and order.pelunasan_due == 3 * 2_500_000


# --- Verifikasi ------------------------------------------------------------------------

def test_antrian_verifikasi_terima_dan_tolak(admin_client, admin):
    fx = make_fanmeet()
    a, b = contoh1(fx, 1), contoh1(fx, 2)
    pa = transitions.submit_payment(a, amount=500_000, actor=CUSTOMER, proof="private/a.jpg")
    pb = transitions.submit_payment(b, amount=400_000, actor=CUSTOMER, proof="private/b.jpg")
    html = admin_client.get("/kelola/verifikasi/").content.decode()
    assert a.code in html and b.code in html and "Rp 500.000" in html

    response = admin_client.post(f"/kelola/verifikasi/{pa.pk}/", {"action": "terima", "amount_received": "500.000"})
    assert response["Location"].endswith(f"p={pb.pk}")  # otomatis lanjut ke bukti berikutnya
    a.refresh_from_db()
    assert a.status == OrderStatus.MENUNGGU_PELUNASAN

    html = admin_client.get(f"/kelola/verifikasi/?p={pb.pk}").content.decode()
    assert "-Rp 100.000" in html  # selisih klaim vs diharapkan
    admin_client.post(f"/kelola/verifikasi/{pb.pk}/", {"action": "tolak", "reason": ""})
    pb.refresh_from_db()
    assert pb.status == PaymentStatus.MENUNGGU  # alasan wajib
    admin_client.post(f"/kelola/verifikasi/{pb.pk}/", {"action": "tolak", "reason": "Nominal tidak sesuai"})
    pb.refresh_from_db()
    b.refresh_from_db()
    assert pb.status == PaymentStatus.DITOLAK and b.status == OrderStatus.MENUNGGU_FEE
    assert "Semua bukti sudah dicek" in admin_client.get("/kelola/verifikasi/").content.decode()


# --- Waiting list & lepas slot -------------------------------------------------------------

def test_waiting_list_naikkan_menolak_bila_kuota_habis(admin_client):
    fx = make_fanmeet(slot_quota=2)
    a = contoh1(fx, 1)
    b = make_order(fx, [line(fx, JASWAR, 1, holder=jaswar_holder(nik="3171019999999999"))], buyer_data=buyer(name="B"))
    assert b.status == OrderStatus.WAITING_LIST
    html = admin_client.get("/kelola/waiting-list/").content.decode()
    assert b.code in html and "disabled" in html
    admin_client.post(f"/kelola/pesanan/{b.code}/aksi/naikkan/")
    b.refresh_from_db()
    assert b.status == OrderStatus.WAITING_LIST
    transitions.cancel_by_customer(a, actor=CUSTOMER)
    admin_client.post(f"/kelola/pesanan/{b.code}/aksi/naikkan/", {"next": "/kelola/waiting-list/"})
    b.refresh_from_db()
    assert b.status == OrderStatus.MENUNGGU_FEE


def test_lepas_slot_lewat_batas_pelunasan(admin_client, admin):
    fx = make_fanmeet()
    order = contoh1(fx, 1)
    pay(order, 500_000, admin)
    with freeze_time(fx.phase.pelunasan_deadline + timedelta(hours=1)):
        # waktu maju berhari-hari → sesi admin idle habis; login ulang
        admin_client.force_login(User.objects.get(username="admin-dash"))
        html = admin_client.get("/kelola/waiting-list/").content.decode()
        assert order.code in html and "Lepas slot" in html
        admin_client.post(f"/kelola/pesanan/{order.code}/aksi/lepas-slot/")
    order.refresh_from_db()
    assert (order.status, order.cancel_reason) == (OrderStatus.HANGUS, "LEWAT_BATAS_PELUNASAN")


# --- run_periodic ---------------------------------------------------------------------------

def test_run_periodic_idempoten(admin):
    fx = make_fanmeet()
    expired = contoh1(fx, 1)
    late = contoh1(fx, 2)
    pay(late, 500_000, admin)
    later = fx.phase.pelunasan_deadline + timedelta(hours=1)
    fx.phase.order_close_at = timezone.now() + timedelta(hours=1)
    fx.phase.save()
    with freeze_time(later):
        call_command("run_periodic", verbosity=0)
        call_command("run_periodic", verbosity=0)  # aman dijalankan ulang
    expired.refresh_from_db()
    late.refresh_from_db()
    fx.phase.refresh_from_db()
    assert expired.status == OrderStatus.DIBATALKAN and expired.cancel_reason == "LEWAT_BATAS_FEE"
    assert late.is_late_pelunasan and late.status == OrderStatus.MENUNGGU_PELUNASAN
    assert fx.phase.status == PhaseStatus.TUTUP
    assert AuditLog.objects.filter(action="order.status", data__to="DIBATALKAN").count() == 1

    pay(late, 7_000_000, admin)  # lunas → tanda lewat batas dihapus
    with freeze_time(later):
        call_command("run_periodic", verbosity=0)
    late.refresh_from_db()
    assert not late.is_late_pelunasan and late.status == OrderStatus.SIAP_WAR
    assert Order.objects.filter(is_late_pelunasan=True).count() == 0
