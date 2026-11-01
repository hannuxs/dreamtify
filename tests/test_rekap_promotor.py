"""Fase 10: ekspor promotor (docs/07 §4), link promotor, rekap keuangan."""
import csv
import io
from datetime import date, datetime

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import Client
from django.utils import timezone
from openpyxl import load_workbook

from apps.core.enums import EventStatus, PaymentKind, SlotResult
from apps.core.models import AuditLog
from apps.events.services import regenerate_promotor_token
from apps.exports import promotor
from apps.exports.promotor_format import DATA_COLUMNS, HIDDEN_NIK
from apps.orders.selectors import orders_with_money
from apps.orders.services import links, settlement, transitions

from .factories import JASTIP, JASWAR, VA_BCA, buyer, jastip_holder, jaswar_holder, line, make_fanmeet, make_order, pay, slots

pytestmark = pytest.mark.django_db
User = get_user_model()
NIK = "3171012345678901"

# Salinan docs/07 §1 — sengaja ditulis ulang di sini agar perubahan tak sengaja terdeteksi
EXPECTED_HEADERS = [
    "Stempel waktu", "Nama Lengkap", "No WA", "Email", "No. KTP", "Jenis Kelamin", "Tanggal Lahir", "Username IG",
    "Jumlah Tiket yang di inginkan", "CAT UTAMA yang di inginkan",
    "CAT Cadangan 1 yang di inginkan (Wajib Beda dari CAT UTAMA)",
    "CAT Cadangan 2 yang di inginkan (Wajib Beda dari CAT 1)", "Punya membership?",
    "No Membership (wajib sudah registrasi presale)", "Jenis Jastip", "Bukti Transfer FEE JASTIP/JASWAR",
    "Metode Pembayaran Tiket", "No WA / IG yg merekomendasikan jastip di Dreamtify",
]


@pytest.fixture(autouse=True)
def setup(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.SITE_URL = "http://testserver"
    call_command("seed_initial", verbosity=0)


def login(client, username, role):
    user = User.objects.create_user(username, password="rahasia-panjang-1", is_staff=True)
    user.groups.add(Group.objects.get(name=role))
    client.force_login(user)
    return client


@pytest.fixture
def owner(client):
    return login(client, "owner-rekap", "Owner")


@pytest.fixture
def staff():
    return login(Client(), "admin-rekap", "Admin")


def paid_order(fx, admin, *, proof=True, **kw):
    order = make_order(fx, [line(fx, JASWAR, 2, holder=jaswar_holder(nik=NIK))], **kw)
    pay(order, 500_000, admin)
    if proof:
        payment = order.payments.get(kind=PaymentKind.FEE)
        payment.proof.save("bukti.jpg", ContentFile(b"gambar"))
    return order


def workbook(response):
    assert response.status_code == 200
    return load_workbook(io.BytesIO(response.content))


def xlsx_url(fx, **query):
    pairs = {"event": fx.event.pk, **query}
    return "/kelola/rekap/promotor.xlsx?" + "&".join(f"{k}={v}" for k, v in pairs.items())


def enable(fx, **kw):
    for key, value in {"promotor_link_enabled": True, **kw}.items():
        setattr(fx.event, key, value)
    fx.event.save()


# --- Format Excel -------------------------------------------------------------------

def test_judul_kolom_persis_form_lama(owner, admin):
    assert [c.title for c in DATA_COLUMNS] == EXPECTED_HEADERS
    fx = make_fanmeet()
    paid_order(fx, admin)
    wb = workbook(owner.get(xlsx_url(fx)))
    assert wb.sheetnames == ["Data", "Hasil", "Rekap"]
    ws = wb["Data"]
    assert [c.value for c in ws[1]] == EXPECTED_HEADERS
    assert ws.freeze_panes == "A2" and ws.auto_filter.ref == "A1:R2"
    assert ws["A1"].fill.fgColor.rgb.endswith("BCE2F5") and ws["A1"].font.bold


def test_isi_baris_format_sel_dan_label(owner, admin):
    fx = make_fanmeet()
    order = paid_order(fx, admin, method=VA_BCA)
    ws = workbook(owner.get(xlsx_url(fx, nik=1)))["Data"]
    row = {EXPECTED_HEADERS[i]: cell for i, cell in enumerate(ws[2])}
    assert row["No. KTP"].value == NIK and row["No. KTP"].data_type == "s" and row["No. KTP"].number_format == "@"
    assert row["No WA"].value == "081234567890" and row["No WA"].data_type == "s"
    created = row["Stempel waktu"]
    assert isinstance(created.value, datetime) and created.number_format == "dd/mm/yyyy hh:mm:ss"
    assert created.value == timezone.localtime(order.created_at).replace(tzinfo=None, microsecond=0)
    assert isinstance(row["Tanggal Lahir"].value, (date, datetime)) and row["Tanggal Lahir"].number_format == "dd/mm/yyyy"
    assert row["Jumlah Tiket yang di inginkan"].value == 2
    assert row["Jenis Jastip"].value == "JASWAR (Jasa War Only : Menggunakan Data Cust)"
    assert row["Metode Pembayaran Tiket"].value == "VA BCA"
    assert row["Punya membership?"].value == "Tidak"


def test_nik_tidak_ikut_tanpa_izin(owner, staff, admin):
    fx = make_fanmeet()
    paid_order(fx, admin)
    for client, url in ((owner, xlsx_url(fx)), (staff, xlsx_url(fx, nik=1))):  # Admin nik=1 diabaikan
        response = client.get(url)
        assert workbook(response)["Data"]["E2"].value == HIDDEN_NIK
    csv_text = staff.get(f"/kelola/rekap/promotor.csv?event={fx.event.pk}&nik=1").content.decode("utf-8-sig")
    assert NIK not in csv_text and HIDDEN_NIK in csv_text
    log = AuditLog.objects.filter(action="export.promotor").first()
    assert log.data["format"] == "csv" and log.data["include_nik"] is False and NIK not in str(log.data)


def test_filter_status_default_dan_belum_bayar(owner, admin):
    fx = make_fanmeet()
    paid_order(fx, admin, buyer_data=buyer(name="Lunas Fee"))
    make_order(fx, [line(fx, JASWAR, 1, holder=jaswar_holder(name="Belum Bayar"))])
    cancelled = make_order(fx, [line(fx, JASWAR, 1, holder=jaswar_holder(name="Sudah Batal"))])
    transitions.cancel_by_admin(cancelled, actor=admin)
    names = lambda url: [r[1].value for r in workbook(owner.get(url))["Data"].iter_rows(min_row=2)]  # noqa: E731
    assert names(xlsx_url(fx)) == ["Rina Putri"]
    assert names(xlsx_url(fx, unpaid=1)) == ["Rina Putri", "Belum Bayar"]


def test_urut_stempel_waktu_dan_filter_tahap(owner, admin):
    fx = make_fanmeet()
    first = paid_order(fx, admin, buyer_data=buyer(name="A"))
    second = paid_order(fx, admin, buyer_data=buyer(name="B"))
    lines = promotor.export_lines(fx.event)
    assert [ln.order_id for ln in lines] == [first.pk, second.pk]
    from apps.events.models import SalePhase
    other = SalePhase.objects.create(event=fx.event, name="Gensale")
    assert promotor.export_lines(fx.event, other) == []
    assert len(promotor.export_lines(fx.event, fx.phase)) == 2


def test_isi_customer_tidak_jadi_rumus(owner, admin):
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 1, holder=jaswar_holder(name='=HYPERLINK("http://jahat","klik")'))])
    pay(order, 250_000, admin)
    order.referral = "@cmd|calc\x07"
    order.save()
    ws = workbook(owner.get(xlsx_url(fx)))["Data"]
    assert ws["B2"].data_type == "s" and ws["B2"].value.startswith("=HYPERLINK")
    rows = list(csv.reader(io.StringIO(owner.get(f"/kelola/rekap/promotor.csv?event={fx.event.pk}").content.decode("utf-8-sig"))))
    assert rows[1][1].startswith("'=") and rows[1][17] == "'@cmd|calc"


def test_csv_utf8_bom_dan_kolom(owner, admin):
    fx = make_fanmeet()
    paid_order(fx, admin, buyer_data=buyer(name="Budi"))
    response = owner.get(f"/kelola/rekap/promotor.csv?event={fx.event.pk}&nik=1")
    assert response.content.startswith(b"\xef\xbb\xbf") and "text/csv" in response["Content-Type"]
    rows = list(csv.reader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0] == EXPECTED_HEADERS and rows[1][4] == NIK
    assert f"Dreamtify_{fx.event.slug}_semua-tahap_" in response["Content-Disposition"]


def test_sheet_hasil_dan_rekap(owner, admin):
    fx = make_fanmeet()
    order = paid_order(fx, admin, method=VA_BCA)
    jastip = make_order(fx, [line(fx, JASTIP, 1, ("CAT 1", "CAT 2", "CAT 3"), holder=jastip_holder())])
    pay(jastip, 2_750_000, admin)
    transitions.start_war(fx.phase, actor=admin)
    s1, s2 = slots(order)
    transitions.set_slot_result(s1, SlotResult.SECURED, actor=admin, category=fx.cat("CAT 1"), ticket_reference="TKT-1")
    transitions.set_slot_result(s2, SlotResult.GAGAL, actor=admin)
    wb = workbook(owner.get(xlsx_url(fx, phase=fx.phase.pk)))
    hasil = wb["Hasil"]
    assert [c.value for c in hasil[1]][:3] == ["Kode Pesanan", "Stempel waktu", "Nama Pemegang"]
    assert hasil.max_row == 4
    assert hasil["H2"].value == "CAT 1" and hasil["I2"].value == "TKT-1"
    rekap = {r[0].value: [c.value for c in r[1:]] for r in wb["Rekap"].iter_rows() if r[0].value}
    assert rekap["Duality Package"][:2] == [2, 0]
    assert rekap["CAT 1"][:2] == [1, 1]
    assert rekap["JASWAR"][:3] == [1, 2, 1] and rekap["JASTIP"][:3] == [1, 1, 0]
    assert rekap["No. KTP"][0] == "Disembunyikan" and rekap["Tahap"][0] == "Presale"


def test_excel_ribuan_baris_tanpa_query_berulang(owner, admin, django_assert_max_num_queries):
    fx = make_fanmeet()
    for i in range(6):
        paid_order(fx, admin, proof=False, buyer_data=buyer(name=f"P{i}"))
    with django_assert_max_num_queries(8):
        lines = promotor.export_lines(fx.event)
        promotor.build_xlsx(fx.event, None, lines, include_nik=False)


# --- Link promotor --------------------------------------------------------------------

def test_halaman_promotor_tanpa_data_pribadi_dan_noindex(admin):
    fx = make_fanmeet()
    enable(fx)
    paid_order(fx, admin)
    url = f"/p/{fx.event.promotor_token}/"
    response = Client().get(url)
    html = response.content.decode()
    assert response.status_code == 200 and response["X-Robots-Tag"].startswith("noindex")
    assert 'content="noindex, nofollow"' in html and "Duality Package" in html and "Unduh Excel" in html
    for private in ("Rina", "081234567890", NIK, "rina@"):
        assert private not in html


def test_link_nonaktif_dan_token_lama_404(admin):
    fx = make_fanmeet()
    url = f"/p/{fx.event.promotor_token}/"
    client = Client()
    assert client.get(url).status_code == 404  # bawaan nonaktif
    enable(fx)
    assert client.get(url).status_code == 200
    regenerate_promotor_token(fx.event, actor=admin)
    assert client.get(url).status_code == 404
    assert client.get(url + "unduh.xlsx").status_code == 404
    assert client.get(f"/p/{fx.event.promotor_token}/").status_code == 200
    fx.event.status = EventStatus.ARSIP
    fx.event.save()
    assert client.get(f"/p/{fx.event.promotor_token}/").status_code == 404


def test_unduh_promotor_mengikuti_izin_nik_dan_tercatat(admin):
    fx = make_fanmeet()
    enable(fx)
    paid_order(fx, admin)
    client = Client(REMOTE_ADDR="10.1.2.3")
    base = f"/p/{fx.event.promotor_token}/unduh"
    assert workbook(client.get(base + ".xlsx"))["Data"]["E2"].value == HIDDEN_NIK
    enable(fx, promotor_include_nik=True)
    assert workbook(client.get(base + ".xlsx"))["Data"]["E2"].value == NIK
    assert client.get(base + ".csv")["Content-Type"].startswith("text/csv")
    assert client.get(base + ".pdf").status_code == 404
    logs = AuditLog.objects.filter(action="export.promotor")
    assert logs.count() == 3 and logs.filter(data__via="link", data__include_nik=True).count() == 2
    assert logs.first().ip_address == "10.1.2.3" and logs.first().actor is None


def test_rate_limit_unduhan_per_token(admin):
    fx = make_fanmeet()
    enable(fx)
    client = Client()
    url = f"/p/{fx.event.promotor_token}/unduh.csv"
    assert all(client.get(url).status_code == 200 for _ in range(30))
    response = client.get(url)
    assert response.status_code == 429 and "Batas unduhan" in response.content.decode()
    assert AuditLog.objects.filter(action="export.promotor").count() == 30


def test_link_bukti_transfer_bertanda_tangan(owner, admin):
    fx = make_fanmeet()
    order = paid_order(fx, admin)
    payment = order.payments.get(kind=PaymentKind.FEE)
    ws = workbook(owner.get(xlsx_url(fx)))["Data"]  # link belum diaktifkan: Excel admin tetap bisa dibuka
    cell = ws["P2"]
    assert cell.hyperlink.target == cell.value and f"/p/{fx.event.promotor_token}/bukti/{payment.pk}/?s=" in cell.value
    client = Client()
    path = cell.value.replace("http://testserver", "")
    response = client.get(path)
    assert response.status_code == 200 and response["X-Content-Type-Options"] == "nosniff"
    assert b"".join(response.streaming_content) == b"gambar"
    assert client.get(f"/p/{fx.event.promotor_token}/bukti/{payment.pk}/").status_code == 404
    assert client.get(f"/p/{fx.event.promotor_token}/bukti/{payment.pk}/?s=palsu").status_code == 404

    other = paid_order(fx, admin, buyer_data=buyer(name="Lain"))
    other_payment = other.payments.get(kind=PaymentKind.FEE)
    swapped = f"/p/{fx.event.promotor_token}/bukti/{other_payment.pk}/?s={path.split('?s=')[1]}"
    assert client.get(swapped).status_code == 404  # tanda tangan terikat id pembayaran
    assert client.get(f"/berkas/bukti/{payment.pk}/?s={path.split('?s=')[1]}").status_code == 404

    regenerate_promotor_token(fx.event, actor=admin)
    assert client.get(path).status_code == 404
    fx.event.refresh_from_db()
    fresh = links.promotor_proof_url(fx.event, payment).replace("http://testserver", "")
    assert client.get(fresh).status_code == 200
    fx.event.status = EventStatus.ARSIP
    fx.event.save()
    assert client.get(fresh).status_code == 404


def test_tab_promotor_menampilkan_unduhan_terakhir(owner, admin):
    fx = make_fanmeet()
    enable(fx)
    paid_order(fx, admin)
    assert "Belum pernah diunduh" in owner.get(f"/kelola/event/{fx.event.pk}/promotor/").content.decode()
    Client().get(f"/p/{fx.event.promotor_token}/unduh.xlsx")
    html = owner.get(f"/kelola/event/{fx.event.pk}/promotor/").content.decode()
    assert "1 kali" in html and "tanpa NIK" in html and "link promotor" in html


# --- Halaman rekap & keuangan -----------------------------------------------------------

def finance_fixture(admin):
    """Campuran: gagal semua, titip dapat kategori lebih murah, kurang bayar, batal, belum final."""
    fx = make_fanmeet()
    gagal = make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))], buyer_data=buyer(name="G"))
    pay(gagal, 7_500_000, admin)
    kurang = make_order(fx, [line(fx, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))], buyer_data=buyer(name="K"))
    pay(kurang, 2_700_000, admin)
    batal = make_order(fx, [line(fx, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))], method=VA_BCA, buyer_data=buyer(name="B"))
    pay(batal, 200_000, admin)
    transitions.cancel_by_customer(batal, actor=admin)  # fee hangus
    menunggu = make_order(fx, [line(fx, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))], method=VA_BCA, buyer_data=buyer(name="M"))
    pay(menunggu, 200_000, admin)
    transitions.start_war(fx.phase, actor=admin)
    for slot in slots(gagal):
        transitions.set_slot_result(slot, SlotResult.GAGAL, actor=admin)
    transitions.set_slot_result(slots(kurang)[0], SlotResult.SECURED, actor=admin, category=fx.cat("Duality Package"))
    return fx, gagal


def test_rekap_keuangan_angka_dan_identitas(admin):
    fx, gagal = finance_fixture(admin)
    transitions.record_refund(gagal, amount=1_000_000, actor=admin, transfer_date=date(2026, 11, 1))
    data, rows = settlement.finance_recap(orders_with_money(fx.event))
    assert data.fee_received + data.pelunasan_received == 7_500_000 + 2_700_000 + 200_000 + 200_000
    assert data.refund_out == 1_000_000
    # gagal: booking 100rb; kurang: fee 250rb + harga 3,5jt; batal: 200rb hangus
    assert data.fee_income == 100_000 + 250_000 + 200_000
    assert data.ticket_price == 3_500_000
    assert data.shortfall == 1_050_000
    assert data.held == (7_400_000 - 1_000_000) + 200_000  # sisa refund + pesanan belum final
    assert data.money_in - data.refund_out == data.fee_income + data.ticket_price + data.held - data.shortfall
    assert len(rows) == 4


def test_halaman_rekap_owner_dan_admin(owner, staff, admin):
    fx, _ = finance_fixture(admin)
    html = owner.get(f"/kelola/rekap/?event={fx.event.pk}").content.decode()
    assert "Pendapatan fee final" in html and "Sertakan No. KTP" in html and "Rp 550.000" in html
    assert "Duality Package" in html
    html = staff.get(f"/kelola/rekap/?event={fx.event.pk}").content.decode()
    assert "Rekap ringkas" in html and "Pendapatan fee final" not in html and "Sertakan No. KTP" not in html


def test_excel_keuangan_hanya_owner(owner, staff, admin):
    fx, gagal = finance_fixture(admin)
    url = f"/kelola/rekap/keuangan.xlsx?event={fx.event.pk}"
    assert staff.get(url).status_code == 403
    wb = workbook(owner.get(url))
    assert wb.sheetnames == ["Ringkasan", "Per pesanan"]
    rows = {r[0].value: r[1].value for r in wb["Ringkasan"].iter_rows(min_row=2)}
    assert rows["Pendapatan fee final"] == 550_000
    assert wb["Per pesanan"].max_row == 5
    assert AuditLog.objects.filter(action="export.finance").exists()


def test_rekap_tanpa_login_dialihkan():
    assert Client().get("/kelola/rekap/").status_code == 302


def test_bayar_sekaligus_dipisah_fee_dan_pelunasan(admin):
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))])
    pay(order, 7_500_000, admin)  # satu Payment jenis FEE
    data, _ = settlement.finance_recap(orders_with_money(fx.event))
    assert (data.fee_received, data.pelunasan_received) == (500_000, 7_000_000)
