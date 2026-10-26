"""Fase 03: login admin, peran, kelola event (tab, publikasi, duplikat), pengaturan, pengguna, log."""
import time

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command

from apps.core.enums import EventStatus, PhaseStatus
from apps.core.models import AuditLog, BankAccount, SiteSetting
from apps.dashboard.middleware import SESSION_KEY
from apps.events.models import Event, FeeRule, SalePhase, TicketCategory

from .factories import JASWAR, line, make_fanmeet, make_order

pytestmark = pytest.mark.django_db
User = get_user_model()
PASSWORD = "rahasia-panjang-1"


@pytest.fixture(autouse=True)
def groups():
    call_command("seed_initial", verbosity=0)


def make_user(username, role=None, **kw):
    user = User.objects.create_user(username, password=PASSWORD, is_staff=True, **kw)
    if role:
        user.groups.add(Group.objects.get(name=role))
    return user


@pytest.fixture
def owner_client(client):
    client.force_login(make_user("owner1", "Owner"))
    return client


@pytest.fixture
def admin_client(client):
    client.force_login(make_user("admin2", "Admin"))
    return client


# --- Login & akses ---------------------------------------------------------

def test_tanpa_login_diarahkan_ke_login(client):
    for url in ("/kelola/", "/kelola/event/", "/kelola/pengaturan/brand/"):
        response = client.get(url)
        assert response.status_code == 302 and response["Location"].startswith("/kelola/login/?next=")


def test_login_berhasil_dan_tercatat(client):
    make_user("owner1", "Owner")
    response = client.post("/kelola/login/", {"username": "owner1", "password": PASSWORD})
    assert response.status_code == 302 and response["Location"] == "/kelola/"
    assert AuditLog.objects.filter(action="auth.login").exists()
    assert client.get("/kelola/").status_code == 200


def test_login_rate_limit_lima_kali_gagal(client):
    make_user("owner1", "Owner")
    for _ in range(5):
        assert client.post("/kelola/login/", {"username": "owner1", "password": "salah"}).status_code == 200
    blocked = client.post("/kelola/login/", {"username": "owner1", "password": PASSWORD})
    assert blocked.status_code == 429  # password benar pun ditolak selama diblokir
    assert "Terlalu banyak percobaan" in blocked.content.decode()


def test_akun_tanpa_peran_tidak_bisa_masuk(client):
    make_user("tamu")
    response = client.post("/kelola/login/", {"username": "tamu", "password": PASSWORD})
    assert response.status_code == 200 and "tidak punya akses" in response.content.decode()


def test_admin_tidak_bisa_membuka_halaman_owner(admin_client):
    assert admin_client.get("/kelola/").status_code == 200
    assert admin_client.get("/kelola/event/").status_code == 200
    for url in ("/kelola/pengaturan/brand/", "/kelola/pengguna/", "/kelola/log/"):
        assert admin_client.get(url).status_code == 403, url
    assert "Pengaturan" not in admin_client.get("/kelola/").content.decode()


def test_owner_bisa_membuka_semua(owner_client):
    for url in ("/kelola/", "/kelola/menu/", "/kelola/event/", "/kelola/event/baru/", "/kelola/pengaturan/brand/",
                "/kelola/pengaturan/rekening/", "/kelola/pengaturan/faq/", "/kelola/pengaturan/syarat/",
                "/kelola/pengaturan/aturan/", "/kelola/pengaturan/template/", "/kelola/pengguna/",
                "/kelola/pengguna/baru/", "/kelola/log/"):
        assert owner_client.get(url).status_code == 200, url


def test_logout_otomatis_setelah_tidak_aktif_2_jam(owner_client):
    session = owner_client.session
    session[SESSION_KEY] = int(time.time()) - 3 * 60 * 60
    session.save()
    response = owner_client.get("/kelola/")
    assert response.status_code == 302 and "/kelola/login/" in response["Location"]


# --- Kelola event ---------------------------------------------------------------

def test_buat_event_lengkap_lewat_tab(owner_client):
    response = owner_client.post("/kelola/event/baru/", {"name": "Contoh Fanmeet", "event_dates": "29–30 Okt 2026",
                                                          "venue": "ICE BSD"})
    event = Event.objects.get(name="Contoh Fanmeet")
    assert response["Location"] == f"/kelola/event/{event.pk}/tahap/"
    assert event.slug == "contoh-fanmeet" and event.status == EventStatus.DRAFT
    assert event.booking_slot_fee == SiteSetting.load().default_booking_slot_fee

    base = f"/kelola/event/{event.pk}"
    owner_client.post(f"{base}/tahap/", {
        "phase-TOTAL_FORMS": "1", "phase-INITIAL_FORMS": "0",
        "phase-0-name": "Presale", "phase-0-sort_order": "0", "phase-0-status": "DRAFT",
        "phase-0-order_open_at": "2026-11-01T10:00", "phase-0-order_close_at": "2026-11-09T10:00",
        "phase-0-war_at": "2026-11-10T12:00", "phase-0-pelunasan_deadline": "2026-11-08T19:00",
        "phase-0-slot_quota": "", "phase-0-membership_label": "No Membership",
    })
    phase = SalePhase.objects.get(event=event)
    assert phase.war_at.hour == 5  # 12.00 WIB disimpan 05.00 UTC

    owner_client.post(f"{base}/kategori/", {
        "cat-TOTAL_FORMS": "2", "cat-INITIAL_FORMS": "0",
        "cat-0-name": "Duality Package", "cat-0-fee_tier": "VIP", "cat-0-price": "3.500.000",
        "cat-0-sort_order": "0", "cat-0-is_active": "on",
        "cat-1-name": "CAT 1", "cat-1-fee_tier": "REGULER", "cat-1-price": "Rp 2,500,000",
        "cat-1-sort_order": "1", "cat-1-is_active": "on",
    })
    assert sorted(TicketCategory.objects.filter(event=event).values_list("price", flat=True)) == [2_500_000, 3_500_000]

    fee = {f"fee__{phase.pk}__{s}__{t}": v for s, t, v in [
        ("JASWAR", "VIP", "250.000"), ("JASWAR", "REGULER", "200.000"),
        ("JASTIP", "VIP", "300.000"), ("JASTIP", "REGULER", "250.000")]}
    response = owner_client.post(f"{base}/fee/", fee, HTTP_HX_REQUEST="true")
    assert response.status_code == 200 and "dt:toast" in response["HX-Trigger"]
    assert FeeRule.objects.filter(phase=phase).count() == 4
    assert AuditLog.objects.filter(action="event.fees").exists()


def test_validasi_publikasi_menolak_fee_belum_lengkap(owner_client):
    fx = make_fanmeet()
    event, phase = fx.event, fx.phase
    phase.fee_rules.filter(service_type="JASTIP", fee_tier="VIP").delete()
    event.status = EventStatus.DRAFT
    event.save()
    data = {"name": event.name, "slug": event.slug, "status": EventStatus.TAMPIL}
    response = owner_client.post(f"/kelola/event/{event.pk}/info/", data)
    assert response.status_code == 200
    assert "matriks fee belum lengkap" in response.content.decode()
    event.refresh_from_db()
    assert event.status == EventStatus.DRAFT  # dibatalkan (rollback)

    # Menghapus sel fee pada event yang sudah tampil juga ditolak
    FeeRule.objects.create(phase=phase, service_type="JASTIP", fee_tier="VIP", fee_per_ticket=300_000)
    owner_client.post(f"/kelola/event/{event.pk}/info/", data)
    event.refresh_from_db()
    assert event.status == EventStatus.TAMPIL
    cells = {f"fee__{phase.pk}__{s}__{t}": "200000" for s in ("JASWAR", "JASTIP") for t in ("VIP", "REGULER")}
    cells[f"fee__{phase.pk}__JASTIP__VIP"] = ""
    owner_client.post(f"/kelola/event/{event.pk}/fee/", cells)
    assert FeeRule.objects.filter(phase=phase, service_type="JASTIP", fee_tier="VIP").exists()


def test_tutup_pesanan_minimal_dua_jam_sebelum_war(owner_client):
    fx = make_fanmeet()
    p = fx.phase
    response = owner_client.post(f"/kelola/event/{fx.event.pk}/tahap/", {
        "phase-TOTAL_FORMS": "1", "phase-INITIAL_FORMS": "1", "phase-0-id": p.pk,
        "phase-0-name": "Presale", "phase-0-sort_order": "0", "phase-0-status": "BUKA",
        "phase-0-order_close_at": "2026-11-10T11:00", "phase-0-war_at": "2026-11-10T12:00",
    })
    assert "Paling lambat 2 jam sebelum war" in response.content.decode()


def test_duplikat_event_menyalin_tanpa_pesanan(owner_client):
    fx = make_fanmeet()
    make_order(fx, [line(fx, JASWAR, 1)])
    response = owner_client.post(f"/kelola/event/{fx.event.pk}/duplikat/")
    copy = Event.objects.exclude(pk=fx.event.pk).get()
    assert response["Location"] == f"/kelola/event/{copy.pk}/info/"
    assert copy.name.endswith("(salinan)") and copy.status == EventStatus.DRAFT
    assert copy.first_show_date is None and copy.promotor_token != fx.event.promotor_token
    assert copy.categories.count() == 4 and copy.orders.count() == 0
    new_phase = copy.phases.get()
    assert new_phase.status == PhaseStatus.DRAFT and new_phase.war_at is None
    assert new_phase.fee_rules.count() == 4


def test_ganti_link_promotor_dan_nik_hanya_owner(owner_client, client):
    fx = make_fanmeet()
    old = fx.event.promotor_token
    owner_client.post(f"/kelola/event/{fx.event.pk}/promotor/", {"action": "regenerate"})
    fx.event.refresh_from_db()
    assert fx.event.promotor_token != old

    client.force_login(make_user("admin3", "Admin"))
    client.post(f"/kelola/event/{fx.event.pk}/promotor/",
                {"promotor_name": "PK Ent", "promotor_link_enabled": "on", "promotor_include_nik": "on"})
    fx.event.refresh_from_db()
    assert fx.event.promotor_name == "PK Ent" and not fx.event.promotor_include_nik


# --- Pengaturan, pengguna, log ------------------------------------------------------

def test_pengaturan_brand_dan_rekening(owner_client):
    owner_client.post("/kelola/pengaturan/brand/", {"brand_name": "Dreamtify", "tagline": "Your Dream is Our Priority",
                                                    "admin_whatsapp": "0812-1111-2222", "instagram": "@dreamtify"})
    site = SiteSetting.load()
    assert (site.admin_whatsapp, site.instagram) == ("6281211112222", "dreamtify")
    bank = BankAccount.objects.get()
    owner_client.post("/kelola/pengaturan/rekening/", {
        "bank-TOTAL_FORMS": "2", "bank-INITIAL_FORMS": "1",
        "bank-0-id": bank.pk, "bank-0-bank_name": "BCA", "bank-0-account_number": bank.account_number,
        "bank-0-account_holder": bank.account_holder, "bank-0-sort_order": "0", "bank-0-is_active": "on",
        "bank-1-bank_name": "Mandiri", "bank-1-account_number": "1230009876543", "bank-1-account_holder": "Dreamtify",
        "bank-1-sort_order": "1", "bank-1-is_active": "on",
    })
    assert BankAccount.objects.count() == 2
    # Tombol WA admin muncul di web publik
    assert "wa.me/6281211112222" in owner_client.get("/").content.decode()


def test_owner_menambah_admin_dan_tidak_bisa_menonaktifkan_diri(owner_client):
    response = owner_client.post("/kelola/pengguna/baru/", {
        "username": "admin9", "first_name": "Sari", "role": "Admin",
        "password1": "kata-sandi-kuat-99", "password2": "kata-sandi-kuat-99"})
    assert response.status_code == 302
    admin9 = User.objects.get(username="admin9")
    assert admin9.groups.filter(name="Admin").exists() and admin9.check_password("kata-sandi-kuat-99")

    me = User.objects.get(username="owner1")
    response = owner_client.post(f"/kelola/pengguna/{me.pk}/", {"first_name": "", "role": "Owner"})  # is_active kosong
    assert "Harus ada minimal satu Owner" in response.content.decode() or \
        "tidak bisa menurunkan" in response.content.decode()
    me.refresh_from_db()
    assert me.is_active

    owner_client.post(f"/kelola/pengguna/{admin9.pk}/sandi/",
                      {"new_password1": "sandi-baru-kuat-77", "new_password2": "sandi-baru-kuat-77"})
    admin9.refresh_from_db()
    assert admin9.check_password("sandi-baru-kuat-77")
    assert AuditLog.objects.filter(action="user.password_reset").exists()


def test_log_aktivitas_bisa_difilter(owner_client):
    fx = make_fanmeet()
    owner_client.post(f"/kelola/event/{fx.event.pk}/duplikat/")
    html = owner_client.get("/kelola/log/?action=event.duplicate").content.decode()
    assert "event.duplicate" in html
    html = owner_client.get("/kelola/log/?action=auth.login").content.decode()
    assert "Duplikat dari" not in html
