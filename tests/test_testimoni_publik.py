"""Fase 11: beranda, testimoni (customer → moderasi → tampil), FAQ/syarat/privasi, SEO, seed_demo."""
import io
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import CommandError, call_command
from django.test import Client
from PIL import Image

from apps.core.enums import EventStatus, OrderStatus, PhaseStatus, SlotResult, TestimonialStatus
from apps.core.models import SiteSetting
from apps.events.models import Event, SalePhase
from apps.orders.models import Order
from apps.orders.services import transitions
from apps.orders.services.links import make_tracking_token
from apps.orders.services.transitions import InvalidTransition
from apps.testimonials import services as testimonials
from apps.testimonials.models import Testimonial

from .factories import CUSTOMER, JASWAR, line, make_fanmeet, make_order, pay, slots

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def setup(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.PUBLIC_MEDIA_ROOT = tmp_path / "public"
    call_command("seed_initial", verbosity=0)


@pytest.fixture
def staff(client):
    user = User.objects.create_user("admin-testi", password="rahasia-panjang-1", is_staff=True)
    user.groups.add(Group.objects.get(name="Admin"))
    client.force_login(user)
    return client


def jpg(name="foto.jpg"):
    buf = io.BytesIO()
    Image.new("RGB", (120, 90), (120, 180, 220)).save(buf, "JPEG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/jpeg")


def finished_order(admin):
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))], method="VA_BCA")
    pay(order, 200_000, admin)
    transitions.start_war(fx.phase, actor=admin)
    transitions.set_slot_result(slots(order)[0], SlotResult.SECURED, actor=admin, category=fx.cat("CAT 3"))
    transitions.set_fulfillment(slots(order)[0], "INFO_DIKIRIM", actor=admin, note="Tukar di booth")
    order.refresh_from_db()
    assert order.status == OrderStatus.SELESAI
    return order


def lacak(client, order):
    return client.get(f"/lacak/{order.code}/?t={make_tracking_token(order)}")


def post_testimonial(client, order, **extra):
    data = {"display_name": "Rina", "rating": "5", "text": "Mantap sekali", "consent": "on", **extra}
    return client.post(f"/lacak/{order.code}/testimoni/", data)


# --- Testimoni customer --------------------------------------------------------------

def test_testimoni_alur_customer_moderasi_tampil(staff, admin):
    order = finished_order(admin)
    customer = Client()
    assert "Bagikan pengalamanmu" in lacak(customer, order).content.decode()
    post_testimonial(customer, order, image=jpg())
    testimonial = Testimonial.objects.get(order=order)
    assert testimonial.status == TestimonialStatus.MENUNGGU and testimonial.image and not testimonial.public_image
    assert testimonial.image.name.startswith("private/")
    html = customer.get("/testimoni/").content.decode()
    assert "Mantap sekali" not in html  # MENUNGGU tidak tampil publik

    html = staff.get("/kelola/testimoni/").content.decode()
    assert "Mantap sekali" in html and order.code in html
    assert staff.get(f"/kelola/testimoni/{testimonial.pk}/gambar/").status_code == 200
    assert customer.get(f"/kelola/testimoni/{testimonial.pk}/gambar/").status_code == 302
    staff.post(f"/kelola/testimoni/{testimonial.pk}/setujui/")
    testimonial.refresh_from_db()
    assert testimonial.status == TestimonialStatus.TAMPIL and testimonial.public_image.name.startswith("public/")
    html = customer.get("/testimoni/").content.decode()
    assert "Mantap sekali" in html and "Pembeli terverifikasi" in html and testimonial.public_image.url in html
    assert "Terima kasih, testimonimu" in lacak(customer, order).content.decode()

    # Disembunyikan → gambar publik ikut hilang
    url, path = testimonial.public_image.url, Path(testimonial.public_image.path)
    staff.post(f"/kelola/testimoni/{testimonial.pk}/sembunyikan/")
    testimonial.refresh_from_db()
    assert not testimonial.public_image and not path.exists() and url not in customer.get("/testimoni/").content.decode()


def test_testimoni_hanya_sekali_dan_hanya_saat_selesai(admin):
    fx = make_fanmeet()
    pending = make_order(fx, [line(fx, JASWAR, 1)])
    customer = Client()
    assert "Bagikan pengalamanmu" not in lacak(customer, pending).content.decode()
    post_testimonial(customer, pending)
    assert not Testimonial.objects.exists()

    order = finished_order(admin)
    lacak(customer, order)
    post_testimonial(customer, order)
    post_testimonial(customer, order, text="Kedua kali")
    assert Testimonial.objects.filter(order=order).count() == 1
    with pytest.raises(InvalidTransition):
        testimonials.submit_from_customer(order, display_name="A", rating=5, text="x", actor=CUSTOMER)


def test_testimoni_butuh_akses_persetujuan_dan_gambar_valid(admin):
    order = finished_order(admin)
    assert Client().post(f"/lacak/{order.code}/testimoni/", {"display_name": "A", "rating": "5", "text": "x", "consent": "on"}).status_code in (302, 404)
    assert not Testimonial.objects.exists()
    customer = Client()
    lacak(customer, order)
    response = customer.post(f"/lacak/{order.code}/testimoni/", {"display_name": "A", "rating": "5", "text": "x"})
    assert "Centang persetujuan" in response.content.decode() and not Testimonial.objects.exists()
    fake = SimpleUploadedFile("x.jpg", b"bukan gambar", content_type="image/jpeg")
    assert post_testimonial(customer, order, image=fake).status_code == 200
    assert not Testimonial.objects.exists()


def test_moderasi_unggulan_edit_hapus_tambah(staff, admin):
    response = staff.post("/kelola/testimoni/tambah/", {"display_name": "Kak Lia", "rating": "5"})
    assert response.status_code == 422 and not Testimonial.objects.exists()
    staff.post("/kelola/testimoni/tambah/", {"display_name": "Kak Lia", "rating": "4", "text": "Sip", "image": jpg()})
    t = Testimonial.objects.get()
    assert t.status == TestimonialStatus.TAMPIL and t.public_image and t.source == "ADMIN"
    staff.post(f"/kelola/testimoni/{t.pk}/unggulan/")
    t.refresh_from_db()
    assert t.is_featured and "Kak Lia" in Client().get("/").content.decode()
    staff.post(f"/kelola/testimoni/{t.pk}/ubah/", {f"t{t.pk}-display_name": "Kak Lia", f"t{t.pk}-text": "Sip banget"})
    t.refresh_from_db()
    assert t.text == "Sip banget"
    paths = [Path(t.image.path), Path(t.public_image.path)]
    staff.post(f"/kelola/testimoni/{t.pk}/hapus/")
    assert not Testimonial.objects.exists() and not any(p.exists() for p in paths)


def test_halaman_testimoni_filter_ringkasan_paginasi(admin):
    fx = make_fanmeet()
    other = make_fanmeet()
    for i in range(13):
        testimonials.create_manual(display_name=f"Orang {i}", rating=4 if i % 2 else 5, text="ok", event=fx.event, actor=admin)
    testimonials.create_manual(display_name="Lainnya", rating=1, text="ok", event=other.event, actor=admin)
    client = Client()
    html = client.get("/testimoni/").content.decode()
    assert "dari 14 testimoni" in html and "Halaman 1 dari 2" in html
    assert "Halaman 2 dari 2" in client.get("/testimoni/?halaman=2").content.decode()
    html = client.get(f"/testimoni/?event={other.event.slug}").content.decode()
    assert "Lainnya" in html and "Orang 1" not in html and "dari 1 testimoni" in html


def test_toggle_unggulan_ditolak_untuk_menunggu(admin):
    t = Testimonial.objects.create(display_name="X", rating=5, text="x")
    with pytest.raises(InvalidTransition):
        testimonials.toggle_featured(t, actor=admin)


def test_kartu_beranda_tugas_menuju_moderasi(staff):
    Testimonial.objects.create(display_name="X", rating=5, text="x")
    assert 'href="/kelola/testimoni/"' in staff.get("/kelola/").content.decode()


# --- Halaman publik ------------------------------------------------------------------

def test_beranda_final(admin):
    fx = make_fanmeet(slot_quota=20)
    testimonials.toggle_featured(testimonials.create_manual(display_name="Kak Unggul", rating=5, text="Bagus", actor=admin), actor=admin)
    testimonials.create_manual(display_name="Kak Biasa", rating=5, text="Bagus", actor=admin)
    html = Client().get("/").content.decode()
    assert "Segera hadir" not in html and fx.event.name in html and "Sisa ±20 slot" in html
    assert "Cara kerja" in html and "JASTIP" in html and "Kak Unggul" in html and "Kak Biasa" not in html
    assert "Apa beda JASWAR dan JASTIP?" in html


def test_beranda_memilih_tahap_relevan_dan_menyembunyikan_event_selesai(admin):
    fx = make_fanmeet()
    second = SalePhase.objects.create(event=fx.event, name="Gensale", status=PhaseStatus.WAR, sort_order=1)
    SalePhase.objects.filter(pk=fx.phase.pk).update(status=PhaseStatus.SELESAI)
    html = Client().get("/").content.decode()
    assert fx.event.name in html and "War berlangsung" in html and "Presale selesai" not in html
    SalePhase.objects.filter(pk=second.pk).update(status=PhaseStatus.SELESAI)
    assert fx.event.name not in Client().get("/").content.decode()


def test_beranda_kosong_tampilkan_ajakan_pantau_ig():
    html = Client().get("/").content.decode()
    assert "Belum ada event, pantau IG kami ya" in html


def test_faq_syarat_privasi_dari_pengaturan():
    client = Client()
    assert "Berapa lama refund diproses?" in client.get("/faq/").content.decode()
    html = client.get("/syarat/").content.decode()
    assert "booking slot" in html and "Syarat &amp; ketentuan" in html
    assert "UU No. 27 Tahun 2022" in client.get("/privasi/").content.decode() or "Undang-Undang" in client.get("/privasi/").content.decode()
    site = SiteSetting.load()
    site.general_terms = "Aturan khusus Owner"
    site.save()
    assert "Aturan khusus Owner" in client.get("/syarat/").content.decode()
    call_command("seed_initial", verbosity=0)
    assert SiteSetting.load().general_terms == "Aturan khusus Owner"  # seed tidak menimpa


def test_robots_dan_sitemap(settings):
    settings.SITE_URL = "https://contoh.test"
    fx = make_fanmeet()
    draft = make_fanmeet()
    Event.objects.filter(pk=draft.event.pk).update(status=EventStatus.DRAFT)
    robots = Client().get("/robots.txt")
    text = robots.content.decode()
    assert robots["Content-Type"].startswith("text/plain")
    for path in ("/kelola/", "/lacak/", "/p/"):
        assert f"Disallow: {path}" in text
    assert "Sitemap: https://contoh.test/sitemap.xml" in text
    xml = Client().get("/sitemap.xml").content.decode()
    assert f"https://contoh.test/event/{fx.event.slug}/" in xml and draft.event.slug not in xml
    assert "/p/" not in xml and "/lacak/" not in xml


def test_open_graph_poster_event(settings):
    settings.SITE_URL = "https://contoh.test"
    fx = make_fanmeet()
    fx.event.poster.save("poster.jpg", jpg())
    html = Client().get(f"/event/{fx.event.slug}/").content.decode()
    assert f'content="https://contoh.test{fx.event.poster.url}"' in html
    assert f'<meta property="og:title" content="{fx.event.name}' in html
    assert 'rel="canonical"' in html


# --- seed_demo -----------------------------------------------------------------------

def test_seed_demo_menolak_di_prod(settings):
    settings.DJANGO_ENV = "prod"
    with pytest.raises(CommandError):
        call_command("seed_demo", verbosity=0)
    assert not Order.objects.exists()


def test_seed_demo_semua_status_dan_idempoten(settings):
    settings.DJANGO_ENV = "dev"
    out = io.StringIO()
    call_command("seed_demo", stdout=out)
    assert "demo-owner" in out.getvalue() and "/lacak/" in out.getvalue()
    statuses = set(Order.objects.values_list("status", flat=True))
    assert statuses == set(OrderStatus.values)
    assert 23 <= Order.objects.count() <= 30
    assert Testimonial.objects.filter(status=TestimonialStatus.TAMPIL, is_featured=True).count() >= 3
    assert Testimonial.objects.filter(status=TestimonialStatus.MENUNGGU).exists()
    # Pesanan SELESAI yang disebut di output belum punya testimoni
    code = out.getvalue().split("/lacak/")[1].split("/")[0]
    assert testimonials.can_submit(Order.objects.get(code=code))

    total = Order.objects.count()
    call_command("seed_demo", stdout=io.StringIO())
    assert Order.objects.count() == total
    call_command("seed_demo", "--reset", stdout=io.StringIO())
    assert Order.objects.count() == total and Event.objects.filter(slug="demo-sky-concert").count() == 1
    html = Client().get("/").content.decode()
    assert "Sky Concert (Demo)" in html and "Dreamy Fanmeet (Demo)" in html
