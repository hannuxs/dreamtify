"""Fase 14: skenario docs/11 §2 lewat halaman sungguhan (customer & admin), plus pemeriksaan N+1."""
import io
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from openpyxl import load_workbook

from apps.core.enums import EventStatus, FulfillmentStatus, OrderStatus, PhaseStatus, TestimonialStatus, VaStatus
from apps.events.models import Event
from apps.exports.promotor_format import DATA_COLUMNS
from apps.notifications.models import Notification
from apps.orders.models import Order, Payment, VaNotice
from apps.orders.services import transitions
from apps.orders.services.links import make_tracking_token
from apps.testimonials.models import Testimonial

from .factories import JASWAR, Fanmeet, line, make_fanmeet, make_order, pay, slots
from .test_form_pesanan import jastip_line, jaswar_line, order_post
from .test_lacak import pay_post, upload

pytestmark = pytest.mark.django_db
User = get_user_model()


@pytest.fixture(autouse=True)
def setup(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    settings.PUBLIC_MEDIA_ROOT = tmp_path / "public"
    settings.SITE_URL = "http://testserver"
    call_command("seed_initial", verbosity=0)


@pytest.fixture
def staff():
    user = User.objects.create_user("owner-akhir", password="rahasia-panjang-1", is_staff=True)
    user.groups.add(Group.objects.get(name="Owner"))
    client = Client()
    client.force_login(user)
    return client


def customer(n):
    return Client(REMOTE_ADDR=f"10.20.0.{n}")


def latest():
    return Order.objects.order_by("-id").first()


def duplicated_event(staff) -> Fanmeet:
    """Skenario 1: duplikat event, atur tanggal, buka tahap."""
    source = make_fanmeet()
    staff.post(f"/kelola/event/{source.event.pk}/duplikat/")
    event = Event.objects.exclude(pk=source.event.pk).get()
    assert event.status == EventStatus.DRAFT
    now = timezone.now()
    Event.objects.filter(pk=event.pk).update(name="Fanmeet Baru", status=EventStatus.TAMPIL,
                                             first_show_date=(now + timedelta(days=30)).date())
    phase = event.phases.get()
    for key, value in (("status", PhaseStatus.BUKA), ("order_open_at", now - timedelta(days=1)),
                       ("order_close_at", now + timedelta(days=3)), ("war_at", now + timedelta(days=4)),
                       ("pelunasan_deadline", now + timedelta(days=3))):
        setattr(phase, key, value)
    phase.save()
    event.refresh_from_db()
    return Fanmeet(event=event, phase=phase, cats={c.name: c for c in event.categories.all()})


def verify(staff, amount):
    payment = Payment.objects.order_by("-id").first()
    staff.post(f"/kelola/verifikasi/{payment.pk}/", {"action": "terima", "amount_received": amount})
    return payment


def post_slot(staff, slot, pick):
    slot.refresh_from_db()
    return staff.post(f"/kelola/war/tiket/{slot.pk}/", {"pick": pick, "version": slot.version}, HTTP_HX_REQUEST="true")


def test_skenario_1_sampai_10_satu_alur(staff):
    fx = duplicated_event(staff)
    assert customer(1).get(f"/event/{fx.event.slug}/").status_code == 200

    # 2. Pesanan multi-baris: 2 VIP JASWAR + 1 CAT 3 JASTIP untuk teman, titip bayar
    rina = customer(1)
    order_post(rina, fx, jaswar_line(fx, 0, 2, ("Duality Package", "CAT 1", "CAT 2")),
               jastip_line(fx, 1, 1, ("CAT 3", "CAT 2", "CAT 1")))
    main = latest()
    assert (main.status, main.fee_due, main.pelunasan_due) == (OrderStatus.MENUNGGU_FEE, 750_000, 9_500_000)
    lacak = f"/lacak/{main.code}/?t={make_tracking_token(main)}"

    # 3. Bukti fee → verifikasi → menunggu pelunasan, Kotak Kabar terisi
    rina.get(lacak)
    pay_post(rina, main, amount="750.000")
    main.refresh_from_db()
    assert main.status == OrderStatus.VERIFIKASI_FEE
    verify(staff, "750.000")
    main.refresh_from_db()
    assert main.status == OrderStatus.MENUNGGU_PELUNASAN
    keys = set(Notification.objects.filter(order=main).values_list("template_key", flat=True))
    assert {"FEE_DITERIMA", "TAGIHAN_PELUNASAN"} <= keys

    # 4. Pelunasan → siap war
    pay_post(rina, main, amount="9.500.000")
    verify(staff, "9.500.000")
    main.refresh_from_db()
    assert main.status == OrderStatus.SIAP_WAR

    # 5. Pesanan VA, lalu waiting list yang naik setelah pesanan lain batal
    budi = customer(2)
    order_post(budi, fx, jaswar_line(fx, 0, 1, ("CAT 3", "CAT 2", "CAT 1"), nik="3171012345670002"), method="VA_BCA")
    va_order = latest()
    budi.get(f"/lacak/{va_order.code}/?t={make_tracking_token(va_order)}")
    pay_post(budi, va_order, amount="200.000")
    verify(staff, "200.000")
    batal = customer(3)
    order_post(batal, fx, jaswar_line(fx, 0, 1, ("CAT 3", "CAT 2", "CAT 1"), nik="3171012345670003"), method="VA_BCA")
    leaving = latest()
    fx.phase.slot_quota = 5
    fx.phase.save(update_fields=["slot_quota"])
    sari = customer(4)
    order_post(sari, fx, jaswar_line(fx, 0, 1, ("CAT 3", "CAT 2", "CAT 1"), nik="3171012345670004"), method="VA_BCA")
    waiting = latest()
    assert waiting.status == OrderStatus.WAITING_LIST
    batal.get(f"/lacak/{leaving.code}/?t={make_tracking_token(leaving)}")
    batal.post(f"/lacak/{leaving.code}/batal/")
    staff.post(f"/kelola/pesanan/{waiting.code}/aksi/naikkan/")
    waiting.refresh_from_db()
    assert waiting.status == OrderStatus.MENUNGGU_FEE
    sari.get(f"/lacak/{waiting.code}/?t={make_tracking_token(waiting)}")
    pay_post(sari, waiting, amount="200.000")
    verify(staff, "200.000")

    # 6. Mode War: mulai, kirim VA, customer klaim, isi hasil
    staff.post(f"/kelola/war/{fx.phase.pk}/mulai/")
    prefix = f"va{va_order.pk}"
    expires = (timezone.localtime() + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M")
    staff.post(f"/kelola/war/pesanan/{va_order.code}/va/", {
        f"{prefix}-bank": "BCA", f"{prefix}-va_number": "8808123456789012", f"{prefix}-amount": "1.500.000",
        f"{prefix}-expires_at": expires, f"{prefix}-slots": [s.pk for s in slots(va_order)]}, HTTP_HX_REQUEST="true")
    va = VaNotice.objects.get(order=va_order)
    assert "8808123456789012" in budi.get(f"/lacak/{va_order.code}/").content.decode()
    budi.post(f"/lacak/{va_order.code}/va/{va.pk}/klaim/")
    staff.post(f"/kelola/war/va/{va.pk}/lunas/")
    va.refresh_from_db()
    assert va.status == VaStatus.LUNAS

    first, second, third = slots(main)
    assert "Dapat Duality Package" in post_slot(staff, first, "primary").content.decode()
    post_slot(staff, second, "gagal")
    post_slot(staff, third, "primary")
    post_slot(staff, slots(va_order)[0], "primary")
    post_slot(staff, slots(waiting)[0], "gagal_customer")
    staff.post(f"/kelola/war/{fx.phase.pk}/selesai/")
    fx.phase.refresh_from_db()
    assert fx.phase.status == PhaseStatus.SELESAI

    # 7. Lacak menampilkan refund benar: bayar 10,25 jt − (3,75 jt + 50 rb + 1,75 jt) = 4,7 jt
    html = rina.get(f"/lacak/{main.code}/").content.decode()
    assert "Rp 4.700.000" in html and "Isi rekening refund" in html
    rina.post(f"/lacak/{main.code}/rekening/", {"bank": "BCA", "number": "1234567890", "holder": "Rina Putri"})
    p = f"r{main.pk}"
    staff.post(f"/kelola/penyelesaian/refund/{main.code}/", {
        f"{p}-amount": "4.700.000", f"{p}-transfer_date": timezone.localdate().isoformat(), f"{p}-proof": upload()})
    refund = Payment.objects.filter(order=main, kind="REFUND").get()
    assert f"/berkas/bukti/{refund.pk}/" in rina.get(f"/lacak/{main.code}/").content.decode()
    assert rina.get(f"/berkas/bukti/{refund.pk}/").status_code == 200

    # 8. Penyerahan JASTIP & info JASWAR
    third.refresh_from_db()
    ids = [third.pk]
    staff.post("/kelola/penyerahan/aksi/", {"slots": ids, "action": "ditukar"})
    staff.post("/kelola/penyerahan/aksi/", {"slots": ids, "action": "siap", "method": "TITIK_TEMU", "detail": "Lobby"})
    staff.post("/kelola/penyerahan/aksi/", {"slots": ids, "action": "diserahkan", "receiver_name": "Teman Rina"})
    third.refresh_from_db()
    assert third.fulfillment_status == FulfillmentStatus.DISERAHKAN
    staff.post("/kelola/penyerahan/aksi/", {"slots": [first.pk], "action": "info", "note": "Booth A"})

    # 9. Selesai → testimoni → disetujui → tampil
    main.refresh_from_db()
    assert main.status == OrderStatus.SELESAI
    rina.post(f"/lacak/{main.code}/testimoni/", {"display_name": "Rina", "rating": "5", "text": "Beres semua", "consent": "on"})
    testimonial = Testimonial.objects.get(order=main)
    assert testimonial.status == TestimonialStatus.MENUNGGU
    staff.post(f"/kelola/testimoni/{testimonial.pk}/setujui/")
    assert "Beres semua" in Client().get("/testimoni/").content.decode()

    # 10. Ekspor Excel & link promotor
    wb = load_workbook(io.BytesIO(staff.get(f"/kelola/rekap/promotor.xlsx?event={fx.event.pk}&nik=1").content))
    assert [c.value for c in wb["Data"][1]] == [c.title for c in DATA_COLUMNS]
    assert "3171012345678901" in [row[4].value for row in wb["Data"].iter_rows(min_row=2)]
    Event.objects.filter(pk=fx.event.pk).update(promotor_link_enabled=True)
    assert Client().get(f"/p/{fx.event.promotor_token}/").status_code == 200
    assert Client().get(f"/p/{fx.event.promotor_token}/unduh.xlsx").status_code == 200


def test_skenario_11_batal_setelah_fee_hangus(staff):
    fx = make_fanmeet()
    client = customer(9)
    order_post(client, fx, jaswar_line(fx, 0, 2, ("Duality Package", "CAT 1", "CAT 2")))
    order = latest()
    client.get(f"/lacak/{order.code}/?t={make_tracking_token(order)}")
    pay_post(client, order, amount="500.000")
    verify(staff, "500.000")
    assert "Rp 500.000" in client.get(f"/lacak/{order.code}/").content.decode()
    client.post(f"/lacak/{order.code}/batal/")
    order.refresh_from_db()
    assert order.status == OrderStatus.HANGUS


# --- N+1 ------------------------------------------------------------------------------

def count_queries(client, url):
    with CaptureQueriesContext(connection) as ctx:
        assert client.get(url).status_code == 200
    return len(ctx)


def test_mode_war_tanpa_n_plus_1(staff, admin):
    fx = make_fanmeet()
    for i in range(2):
        pay(make_order(fx, [line(fx, JASWAR, 2, ("CAT 3", "CAT 2", "CAT 1"))], method="VA_BCA"), 400_000, admin)
    transitions.start_war(fx.phase, actor=admin)
    url = f"/kelola/war/{fx.phase.pk}/"
    staff.get(url)
    few = count_queries(staff, url)
    Order.objects.filter(event=fx.event).delete()
    for i in range(8):
        order = make_order(fx, [line(fx, JASWAR, 2, ("CAT 3", "CAT 2", "CAT 1"))], method="VA_BCA", enforce_schedule=False)
        pay(order, 400_000, admin)
    Order.objects.filter(event=fx.event, status=OrderStatus.SIAP_WAR).update(status=OrderStatus.PROSES_WAR)
    assert count_queries(staff, url) <= few + 2


def test_lacak_tanpa_n_plus_1(admin):
    fx = make_fanmeet()
    small = make_order(fx, [line(fx, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))])
    big = make_order(fx, [line(fx, JASWAR, 4, ("CAT 3", "CAT 2", "CAT 1")) for _ in range(4)])
    client = Client()
    urls = [f"/lacak/{o.code}/?t={make_tracking_token(o)}" for o in (small, big)]
    client.get(urls[0])
    few = count_queries(client, urls[0])
    client.get(urls[1])
    assert count_queries(client, urls[1]) <= few + 2
