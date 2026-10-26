"""Fase 08 (refund, kekurangan, penyerahan) & fase 09 (Kotak Kabar, template, pengingat, email)."""
import io
from datetime import timedelta
from urllib.parse import unquote

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client
from freezegun import freeze_time
from openpyxl import load_workbook
from PIL import Image

from apps.core.enums import FulfillmentStatus, NotificationStatus, OrderStatus, PaymentKind, SlotResult
from apps.core.models import AuditLog, SiteSetting
from apps.notifications.models import MessageTemplate, Notification
from apps.orders.models import Payment
from apps.orders.services import transitions, updates
from apps.orders.services.links import make_tracking_token

from .factories import CUSTOMER, JASTIP, JASWAR, VA_BCA, buyer, jastip_holder, line, make_fanmeet, make_order, pay, slots

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def setup(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    call_command("seed_initial", verbosity=0)


def login(client, username, role):
    user = User.objects.create_user(username, password="rahasia-panjang-1", is_staff=True)
    user.groups.add(Group.objects.get(name=role))
    client.force_login(user)
    return client


@pytest.fixture
def staff(client):
    return login(client, "admin-selesai", "Admin")


def jpg(name="bukti.jpg"):
    buf = io.BytesIO()
    Image.new("RGB", (300, 200), (200, 220, 240)).save(buf, "JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def gagal_semua(fx, admin):
    """Contoh 2: refund 7.400.000."""
    order = make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))])
    pay(order, 7_500_000, admin)
    transitions.start_war(fx.phase, actor=admin)
    for s in slots(order):
        transitions.set_slot_result(s, SlotResult.GAGAL, actor=admin)
    order.refresh_from_db()
    return order


# --- Fase 08: refund -------------------------------------------------------------------

def test_refund_bertahap_dengan_bukti_sampai_selesai(staff, admin):
    order = gagal_semua(make_fanmeet(), admin)
    html = staff.get("/kelola/penyelesaian/").content.decode()
    assert order.code in html and "Rp 7.400.000" in html and "Menunggu customer mengisi rekening" in html
    updates.set_refund_account(order, bank="BCA", number="1234567890", holder="Rina Putri", actor=CUSTOMER)
    html = staff.get("/kelola/penyelesaian/").content.decode()
    assert "1234567890" in html  # admin melihat rekening penuh (tercatat audit)
    assert AuditLog.objects.filter(action="refund.view_accounts").exists()

    p = f"r{order.pk}"
    staff.post(f"/kelola/penyelesaian/refund/{order.code}/", {
        f"{p}-amount": "4.000.000", f"{p}-transfer_date": "2026-11-01", f"{p}-proof": jpg()})
    order.refresh_from_db()
    assert order.status == OrderStatus.PENYELESAIAN
    staff.post(f"/kelola/penyelesaian/refund/{order.code}/", {
        f"{p}-amount": "9.000.000", f"{p}-transfer_date": "2026-11-01"})  # melebihi saldo → ditolak
    assert Payment.objects.filter(order=order, kind=PaymentKind.REFUND).count() == 1
    staff.post(f"/kelola/penyelesaian/refund/{order.code}/", {
        f"{p}-amount": "3.400.000", f"{p}-transfer_date": "2026-11-02"})
    order.refresh_from_db()
    assert order.status == OrderStatus.SELESAI
    refund = Payment.objects.filter(order=order, kind=PaymentKind.REFUND).first()
    customer = Client()
    html = customer.get(f"/lacak/{order.code}/?t={make_tracking_token(order)}").content.decode()
    assert "Refund ditransfer" in html and f"/berkas/bukti/{refund.pk}/" in html
    assert customer.get(f"/berkas/bukti/{refund.pk}/").status_code == 200


def test_export_refund_excel(staff, admin):
    order = gagal_semua(make_fanmeet(), admin)
    updates.set_refund_account(order, bank="BCA", number="0012345678", holder="Rina", actor=CUSTOMER)
    response = staff.get("/kelola/penyelesaian/refund.xlsx")
    assert response.status_code == 200 and "spreadsheetml" in response["Content-Type"]
    ws = load_workbook(io.BytesIO(response.content))["Refund"]
    assert [c.value for c in ws[1]][:6] == ["Kode", "Nama pemesan", "Bank", "No. rekening", "Atas nama", "Nominal"]
    assert ws["D2"].value == "0012345678" and ws["D2"].number_format == "@"  # nol di depan tetap ada
    assert ws["F2"].value == 7_400_000
    assert AuditLog.objects.filter(action="export.refund").exists()


def test_kekurangan_dan_kabar(staff, admin):
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))])
    pay(order, 2_700_000, admin)
    transitions.start_war(fx.phase, actor=admin)
    transitions.set_slot_result(slots(order)[0], SlotResult.SECURED, actor=admin, category=fx.cat("Duality Package"))
    html = staff.get("/kelola/penyelesaian/?tab=kekurangan").content.decode()
    assert order.code in html and "Rp 1.050.000" in html
    before = Notification.objects.filter(order=order, template_key="KEKURANGAN_BAYAR").count()
    staff.post(f"/kelola/penyelesaian/ingatkan/{order.code}/kekurangan/")
    assert Notification.objects.filter(order=order, template_key="KEKURANGAN_BAYAR").count() == before + 1


# --- Fase 08: penyerahan -------------------------------------------------------------------

def test_penyerahan_jastip_massal_dan_jaswar_info(staff, admin):
    fx = make_fanmeet()
    jastip = make_order(fx, [line(fx, JASTIP, 2, ("CAT 3", "CAT 2", "CAT 1"), holder=jastip_holder())], method=VA_BCA)
    jaswar = make_order(fx, [line(fx, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))], method=VA_BCA,
                        buyer_data=buyer(name="Budi"))
    pay(jastip, 500_000, admin)
    pay(jaswar, 200_000, admin)
    transitions.start_war(fx.phase, actor=admin)
    for order in (jastip, jaswar):
        for s in slots(order):
            transitions.set_slot_result(s, SlotResult.SECURED, actor=admin, category=fx.cat("CAT 3"))
    ids = [s.pk for s in slots(jastip)]
    html = staff.get("/kelola/penyerahan/?service=JASTIP").content.decode()
    assert jastip.code in html and jaswar.code not in html

    staff.post("/kelola/penyerahan/aksi/", {"slots": ids, "action": "ditukar"})
    staff.post("/kelola/penyerahan/aksi/", {"slots": ids, "action": "siap"})  # tanpa metode → ditolak
    assert all(s.fulfillment_status == FulfillmentStatus.DITUKAR for s in slots(jastip))
    staff.post("/kelola/penyerahan/aksi/", {"slots": ids, "action": "siap", "method": "TITIK_TEMU",
                                            "detail": "Sab 10.00 lobby GBK"})
    assert Notification.objects.filter(order=jastip, template_key="GELANG_SIAP").count() == 2
    staff.post("/kelola/penyerahan/aksi/", {"slots": ids, "action": "diserahkan", "receiver_name": "Dodi",
                                            "photo": jpg("foto.jpg")})
    jastip.refresh_from_db()
    assert jastip.status == OrderStatus.SELESAI
    assert all(s.handover_photo for s in slots(jastip))  # foto tersalin ke setiap tiket

    slot = slots(jaswar)[0]
    staff.post("/kelola/penyerahan/aksi/", {"slots": [slot.pk], "action": "info", "note": "Tukar di booth A",
                                            "eticket": jpg("etiket.jpg")})
    jaswar.refresh_from_db()
    slot.refresh_from_db()
    assert jaswar.status == OrderStatus.SELESAI and slot.eticket_file
    customer = Client()
    html = customer.get(f"/lacak/{jaswar.code}/?t={make_tracking_token(jaswar)}").content.decode()
    assert "Unduh e-tiket" in html
    assert customer.get(f"/berkas/etiket/{slot.pk}/").status_code == 200

    response = staff.get("/kelola/penyerahan/gelang.xlsx")
    ws = load_workbook(io.BytesIO(response.content))["Penyerahan"]
    assert ws["I1"].value == "Tanda tangan penerima" and ws.max_row == 3


def test_kartu_beranda_penyelesaian(staff, admin):
    order = gagal_semua(make_fanmeet(), admin)
    html = staff.get("/kelola/").content.decode()
    assert "Refund menunggu rekening" in html and "Tiket menunggu penyerahan" in html
    assert order.code  # data dibuat


# --- Fase 09: Kotak Kabar ----------------------------------------------------------------

def test_kotak_kabar_kirim_lewati_ubah(staff, admin):
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 2)])
    pay(order, 500_000, admin)  # FEE_DITERIMA + TAGIHAN_PELUNASAN
    html = staff.get("/kelola/kabar/").content.decode()
    assert "Fee diterima" in html and "Tagihan pelunasan" in html
    fee = Notification.objects.get(order=order, template_key="FEE_DITERIMA")
    response = staff.get(f"/kelola/kabar/{fee.pk}/kirim/")
    assert response.status_code == 302
    url = response["Location"]
    assert url.startswith("https://wa.me/6281234567890?text=") and order.code in unquote(url)
    fee.refresh_from_db()
    assert fee.status == NotificationStatus.TERKIRIM and fee.sent_by.username == "admin-selesai"

    tagihan = Notification.objects.get(order=order, template_key="TAGIHAN_PELUNASAN")
    staff.post(f"/kelola/kabar/{tagihan.pk}/ubah/", {"text": "Halo kak, pesan khusus " + order.code})
    tagihan.refresh_from_db()
    assert tagihan.rendered_text.startswith("Halo kak, pesan khusus")
    html = staff.get("/kelola/kabar/beruntun/").content.decode()
    assert "pesan khusus" in html and "Kirim &amp; lanjut" in html
    staff.post(f"/kelola/kabar/{tagihan.pk}/lewati/")
    tagihan.refresh_from_db()
    assert tagihan.status == NotificationStatus.DILEWATI
    assert "Semua kabar terkirim" in staff.get("/kelola/kabar/beruntun/").content.decode()


def test_kabar_manual_dari_detail_pesanan(staff):
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 1)])
    staff.post(f"/kelola/pesanan/{order.code}/kabar/", {"key": "PENGINGAT_FEE"})
    staff.post(f"/kelola/pesanan/{order.code}/kabar/", {"key": "PENGINGAT_FEE"})  # manual boleh berulang
    notes = Notification.objects.filter(order=order, template_key="PENGINGAT_FEE")
    assert notes.count() == 2 and "Rp 250.000" in notes.first().rendered_text


def test_pengingat_tidak_ganda(admin):
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 2)])
    with freeze_time(order.fee_deadline - timedelta(hours=2)):
        call_command("run_periodic", verbosity=0)
        call_command("run_periodic", verbosity=0)
    assert Notification.objects.filter(order=order, template_key="PENGINGAT_FEE").count() == 1
    pay(order, 500_000, admin)
    with freeze_time(fx.phase.pelunasan_deadline - timedelta(hours=5)):
        call_command("run_periodic", verbosity=0)
        call_command("run_periodic", verbosity=0)
    reminders = Notification.objects.filter(order=order, template_key="PENGINGAT_PELUNASAN")
    assert reminders.count() == 1 and "Rp 7.000.000" in reminders.get().rendered_text


def test_email_otomatis_bila_diaktifkan(admin, django_capture_on_commit_callbacks):
    site = SiteSetting.load()
    site.email_notifications_enabled = True
    site.save()
    fx = make_fanmeet()
    with django_capture_on_commit_callbacks(execute=True):
        order = make_order(fx, [line(fx, JASWAR, 1)])
    assert len(mail.outbox) == 1 and order.code in mail.outbox[0].subject
    note = Notification.objects.get(order=order, channel="EMAIL")
    assert note.status == NotificationStatus.TERKIRIM
    # PESANAN_DIBUAT hanya email → tidak masuk Kotak Kabar WA
    assert not Notification.objects.filter(order=order, channel="WA").exists()


def test_email_mati_secara_default():
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 1)])
    assert not Notification.objects.filter(order=order, channel="EMAIL").exists() and not mail.outbox


# --- Fase 09: template pesan -------------------------------------------------------------

def test_edit_template_pratinjau_peringatan_dan_reset(client):
    owner = login(client, "owner-tpl", "Owner")
    html = owner.get("/kelola/pengaturan/template/").content.decode()
    assert "Fee diterima" in html
    owner.post("/kelola/pengaturan/template/FEE_DITERIMA/", {
        "title": "Fee diterima", "body": "Hai {nama}, {kode} beres {link_lacak} {salah_ketik}",
        "is_active": "on", "send_email": "on"})
    tpl = MessageTemplate.objects.get(key="FEE_DITERIMA")
    assert tpl.is_customized
    html = owner.get("/kelola/pengaturan/template/FEE_DITERIMA/").content.decode()
    assert "Placeholder tak dikenal" in html and "salah_ketik" in html and "DRM-7KX2QP" in html  # pratinjau
    call_command("seed_initial", verbosity=0)
    tpl.refresh_from_db()
    assert "salah_ketik" in tpl.body  # seed tidak menimpa template yang diubah
    owner.post("/kelola/pengaturan/template/FEE_DITERIMA/", {"action": "default"})
    tpl.refresh_from_db()
    assert not tpl.is_customized and "salah_ketik" not in tpl.body


def test_admin_tidak_bisa_edit_template(staff):
    assert staff.get("/kelola/pengaturan/template/FEE_DITERIMA/").status_code == 403
