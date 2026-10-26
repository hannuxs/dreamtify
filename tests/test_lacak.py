"""Fase 05: lacak pesanan, upload bukti aman, berkas privat, batal, ubah data, rekening refund."""
import io
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.utils import timezone
from freezegun import freeze_time
from PIL import Image

from apps.core.enums import OrderStatus, PaymentStatus
from apps.core.models import AuditLog
from apps.core.uploads import process_private_upload
from apps.orders.models import Order, Payment
from apps.orders.services import guidance, settlement, transitions
from apps.orders.services.links import make_tracking_token

from .factories import CUSTOMER, JASTIP, JASWAR, buyer, jaswar_holder, line, make_order, pay, set_results

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.PUBLIC_MEDIA_ROOT = tmp_path / "public"


def jpeg_bytes(exif_model=None, size=(800, 600)) -> bytes:
    img = Image.new("RGB", size, (120, 180, 220))
    buf = io.BytesIO()
    kwargs = {}
    if exif_model:
        exif = Image.Exif()
        exif[0x0110] = exif_model  # Model
        exif[0x010F] = "PabrikRahasia"  # Make
        kwargs["exif"] = exif.tobytes()
    img.save(buf, "JPEG", **kwargs)
    return buf.getvalue()


def upload(name="bukti.jpg", data=None, content_type="image/jpeg"):
    return SimpleUploadedFile(name, data if data is not None else jpeg_bytes(), content_type=content_type)


def contoh1(fx):
    return make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))])


def lacak_client(order) -> Client:
    c = Client()
    c.get(f"/lacak/{order.code}/?t={make_tracking_token(order)}")
    return c


def pay_post(client, order, **extra):
    data = {"amount": "500.000", "sender_name": "Rina", "sender_bank": "BCA", "transfer_date": "2026-10-26",
            "proof": upload()}
    data.update(extra)
    return client.post(f"/lacak/{order.code}/bayar/", data)


# --- Masuk lacak ---------------------------------------------------------------

def test_masuk_dengan_kode_dan_wa(client, fanmeet):
    order = contoh1(fanmeet)
    response = client.post("/lacak/", {"code": order.code[4:].lower(), "whatsapp": "0812 3456 7890"})
    assert response.status_code == 302 and response["Location"] == f"/lacak/{order.code}/"
    html = client.get(response["Location"]).content.decode()
    assert order.code in html and "Yang perlu kamu lakukan sekarang" in html and "Rp 500.000" in html


def test_masuk_salah_pesan_umum(client, fanmeet):
    order = contoh1(fanmeet)
    wrong_wa = client.post("/lacak/", {"code": order.code, "whatsapp": "081299999999"}).content.decode()
    wrong_code = client.post("/lacak/", {"code": "DRM-ZZZZZZ", "whatsapp": "081234567890"}).content.decode()
    for html in (wrong_wa, wrong_code):
        assert "Kode atau nomor WA tidak cocok" in html
    assert client.get(f"/lacak/{order.code}/").status_code == 404


def test_rate_limit_masuk_lacak(client, fanmeet):
    order = contoh1(fanmeet)
    for _ in range(10):
        client.post("/lacak/", {"code": order.code, "whatsapp": "081299999999"})
    blocked = client.post("/lacak/", {"code": order.code, "whatsapp": "081234567890"})
    assert blocked.status_code == 429 and client.get(f"/lacak/{order.code}/").status_code == 404


def test_token_lacak_dan_kedaluwarsa(fanmeet):
    order = contoh1(fanmeet)
    token = make_tracking_token(order)
    c = Client()
    assert c.get(f"/lacak/{order.code}/?t={token}").status_code == 200
    assert c.get(f"/lacak/{order.code}/").status_code == 200  # izin dicatat di session
    with freeze_time(timezone.now() + timedelta(days=31)):
        assert Client().get(f"/lacak/{order.code}/?t={token}").status_code == 404
    assert Client().get(f"/lacak/{order.code}/?t={token}x").status_code == 404


def test_customer_a_tidak_bisa_buka_pesanan_b(fanmeet, admin):
    a = contoh1(fanmeet)
    b = make_order(fanmeet, [line(fanmeet, JASWAR, 1, holder=jaswar_holder(nik="3171019999999999"))],
                   buyer_data=buyer(name="Budi", whatsapp="081211112222"))
    proof_b = transitions.submit_payment(b, amount=250_000, actor=admin, proof=process_private_upload(upload()))
    ca = lacak_client(a)
    assert ca.get(f"/lacak/{b.code}/").status_code == 404
    assert ca.get(f"/berkas/bukti/{proof_b.pk}/").status_code == 404
    assert ca.post(f"/lacak/{b.code}/batal/").status_code == 404
    cb = lacak_client(b)
    response = cb.get(f"/berkas/bukti/{proof_b.pk}/")
    assert response.status_code == 200 and response["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in response["Cache-Control"]


# --- Upload bukti ------------------------------------------------------------------

def test_upload_bukti_fee_jadi_verifikasi(fanmeet):
    order = contoh1(fanmeet)
    c = lacak_client(order)
    response = pay_post(c, order)
    assert response.status_code == 302
    order.refresh_from_db()
    assert order.status == OrderStatus.VERIFIKASI_FEE
    payment = Payment.objects.get(order=order)
    assert payment.amount_claimed == 500_000 and payment.status == PaymentStatus.MENUNGGU
    assert payment.proof.name.startswith("private/") and payment.proof.name.endswith(".jpg")
    assert "bukti" not in payment.proof.name.split("/")[-1]  # nama file UUID
    assert "Bukti fee sedang dicek" in c.get(f"/lacak/{order.code}/").content.decode()
    assert Client().get(f"/berkas/bukti/{payment.pk}/").status_code == 404
    staff = get_user_model().objects.create_user("staf", password="x", is_superuser=True)
    admin_client = Client()
    admin_client.force_login(staff)
    assert admin_client.get(f"/berkas/bukti/{payment.pk}/").status_code == 200


def test_upload_file_palsu_ditolak(fanmeet):
    order = contoh1(fanmeet)
    c = lacak_client(order)
    html = pay_post(c, order, proof=upload("bukti.jpg", b"ini bukan gambar, cuma teks")).content.decode()
    assert "bukan gambar yang valid" in html
    assert not Payment.objects.exists()


def test_upload_terlalu_besar_ditolak(fanmeet):
    order = contoh1(fanmeet)
    c = lacak_client(order)
    big = upload("besar.jpg", b"\xff\xd8" + b"0" * (10 * 1024 * 1024 + 10))
    assert "maksimal 10 MB" in pay_post(c, order, proof=big).content.decode()
    assert not Payment.objects.exists()


def test_exif_dibuang_dan_pdf_diterima():
    processed = process_private_upload(upload(data=jpeg_bytes(exif_model="iPhone Rahasia")))
    data = processed.read()
    assert b"Rahasia" not in data and b"PabrikRahasia" not in data
    assert not Image.open(io.BytesIO(data)).getexif()
    big = process_private_upload(upload(data=jpeg_bytes(size=(4000, 3000))))
    assert Image.open(io.BytesIO(big.read())).width == 2000
    pdf = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
    assert process_private_upload(upload("bukti.pdf", pdf, "application/pdf")).name.endswith(".pdf")
    with pytest.raises(ValidationError):
        process_private_upload(upload("rusak.pdf", b"%PDF-1.4 tanpa akhir", "application/pdf"))


def test_rate_limit_upload_per_pesanan(fanmeet):
    order = contoh1(fanmeet)
    c = lacak_client(order)
    for _ in range(10):
        pay_post(c, order, amount="1")
    assert "Terlalu banyak upload" in pay_post(c, order).content.decode()


# --- Batal, ubah data, rekening refund --------------------------------------------

def test_batal_sebelum_bayar(fanmeet):
    order = contoh1(fanmeet)
    c = lacak_client(order)
    assert "Belum ada pembayaran" in c.get(f"/lacak/{order.code}/").content.decode()
    c.post(f"/lacak/{order.code}/batal/")
    order.refresh_from_db()
    assert order.status == OrderStatus.DIBATALKAN


def test_batal_setelah_fee_hangus_dengan_nominal(fanmeet, admin):
    order = contoh1(fanmeet)
    pay(order, 7_500_000, admin)
    c = lacak_client(order)
    html = c.get(f"/lacak/{order.code}/").content.decode()
    assert "Fee <strong>Rp 500.000</strong> hangus" in html and "Rp 7.000.000" in html
    c.post(f"/lacak/{order.code}/batal/")
    order.refresh_from_db()
    assert order.status == OrderStatus.HANGUS
    html = c.get(f"/lacak/{order.code}/").content.decode()
    assert "Isi rekening refund" in html
    c.post(f"/lacak/{order.code}/rekening/", {"bank": "BCA", "number": "1234-567-890", "holder": "Rina Putri"})
    order = Order.objects.get(pk=order.pk)
    assert order.refund_account_number == "1234567890"
    html = c.get(f"/lacak/{order.code}/").content.decode()
    assert "1234567890" not in html and "••••••7890" in html and "Refund sedang diproses" in html


def test_ubah_pemegang_sebelum_war_dan_ditolak_setelah_war(fanmeet, admin):
    order = contoh1(fanmeet)
    c = lacak_client(order)
    ln = order.lines.get()
    data = {"name": "Rina Putri Baru", "whatsapp": "081234567890", "gender": "P", "birth_date": "2000-05-17",
            "email": "rina@example.com", "instagram": "rinabaru", "nik": ""}
    assert c.post(f"/lacak/{order.code}/pemegang/{ln.pk}/", data).status_code == 302
    ln.refresh_from_db()
    assert ln.holder_name == "Rina Putri Baru" and ln.holder_nik_last4 == "8901"  # NIK kosong = tetap
    assert AuditLog.objects.filter(action="order.holder_update").exists()

    pay(order, 7_500_000, admin)
    transitions.start_war(fanmeet.phase, actor=admin)
    response = c.post(f"/lacak/{order.code}/pemegang/{ln.pk}/", {**data, "name": "Ganti Saat War"})
    assert response.status_code == 302
    ln.refresh_from_db()
    assert ln.holder_name == "Rina Putri Baru"
    assert c.post(f"/lacak/{order.code}/batal/").status_code == 302
    order.refresh_from_db()
    assert order.status == OrderStatus.PROSES_WAR  # tidak bisa batal sendiri sejak war


def test_halaman_sukses_punya_form_upload(client, fanmeet):
    order = contoh1(fanmeet)
    html = client.get(f"/pesanan/{order.code}/berhasil/?t={make_tracking_token(order)}").content.decode()
    assert f'action="/lacak/{order.code}/bayar/"' in html and 'enctype="multipart/form-data"' in html


# --- next_action -------------------------------------------------------------------

def test_next_action_mengikuti_status(fanmeet, admin):
    order = contoh1(fanmeet)
    assert guidance.next_action(order).action == "upload"
    pay(order, 500_000, admin)
    order.refresh_from_db()
    action = guidance.next_action(order)
    assert action.action == "upload" and "Rp 7.000.000" in action.title
    pay(order, 7_000_000, admin)
    order.refresh_from_db()
    assert guidance.next_action(order).title.startswith("Siap war")
    transitions.start_war(fanmeet.phase, actor=admin)
    set_results(order, admin, ("GAGAL", None), ("GAGAL", None))
    assert guidance.next_action(order).action == "refund_account"
    assert settlement.summarize(order).refund_due == 7_400_000


def test_jastip_lacak_tanpa_data_ktp(client, fanmeet):
    order = make_order(fanmeet, [line(fanmeet, JASTIP, 1, ("CAT 3", "CAT 2", "CAT 1"))], method="VA_BCA")
    html = lacak_client(order).get(f"/lacak/{order.code}/").content.decode()
    assert "Dodi" in html and "KTP ••••" not in html
    assert CUSTOMER  # aktor customer tersedia untuk service lain
