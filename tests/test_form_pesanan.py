"""Fase 04: detail event, form pesanan multi-baris, ringkasan live, halaman sukses."""
import re

import pytest
from django.contrib.auth import get_user_model
from django.test import Client

from apps.core.enums import EventStatus, OrderStatus, PhaseStatus
from apps.orders.models import Order, TicketSlot
from apps.orders.services.links import make_tracking_token

from .factories import make_fanmeet

pytestmark = pytest.mark.django_db
NIK = "3171012345678901"


def token_of(client, fx):
    html = client.get(f"/event/{fx.event.slug}/pesan/?tahap={fx.phase.pk}").content.decode()
    return re.search(r'name="form_token" value="([^"]+)"', html).group(1)


def jaswar_line(fx, i, qty, cats, nik=NIK, name="Rina Putri"):
    return {
        f"lines-{i}-service_type": "JASWAR", f"lines-{i}-quantity": str(qty),
        f"lines-{i}-primary": str(fx.cat(cats[0]).pk), f"lines-{i}-backup1": str(fx.cat(cats[1]).pk),
        f"lines-{i}-backup2": str(fx.cat(cats[2]).pk),
        f"lines-{i}-holder_name": name, f"lines-{i}-holder_whatsapp": "081234567890",
        f"lines-{i}-holder_nik": nik, f"lines-{i}-holder_gender": "P",
        f"lines-{i}-holder_birth_date": "2000-05-17", f"lines-{i}-holder_email": "rina@example.com",
        f"lines-{i}-holder_instagram": "rinaputri",
    }


def jastip_line(fx, i, qty, cats, name="Teman Rina"):
    return {
        f"lines-{i}-service_type": "JASTIP", f"lines-{i}-quantity": str(qty),
        f"lines-{i}-primary": str(fx.cat(cats[0]).pk), f"lines-{i}-backup1": str(fx.cat(cats[1]).pk),
        f"lines-{i}-backup2": str(fx.cat(cats[2]).pk),
        f"lines-{i}-holder_name": name, f"lines-{i}-holder_whatsapp": "081298765432",
    }


def order_post(client, fx, *lines, method="TITIP_BAYAR", **extra):
    data = {
        "phase": fx.phase.pk, "form_token": extra.pop("token", None) or token_of(client, fx),
        "buyer-name": "Rina Putri", "buyer-whatsapp": "0812-3456-7890", "buyer-email": "rina@example.com",
        "buyer-instagram": "@rinaputri", "buyer-referral": "",
        "pay-payment_method": method, "agree-agree_terms": "on", "agree-agree_privacy": "on",
    }
    for ln in lines:
        data.update(ln)
    data.update(extra)
    return client.post(f"/event/{fx.event.slug}/pesan/", data)


CONTOH4 = (("Duality Package", "CAT 1", "CAT 2"), ("CAT 3", "CAT 2", "CAT 1"))


# --- Detail event ---------------------------------------------------------------

def test_detail_event_menampilkan_pricelist_dan_tombol(client):
    fx = make_fanmeet()
    html = client.get(f"/event/{fx.event.slug}/").content.decode()
    assert "Duality Package" in html and "Rp 3.500.000" in html
    assert "Rp 250.000" in html  # fee JASWAR VIP
    assert f"/event/{fx.event.slug}/pesan/?tahap={fx.phase.pk}" in html


def test_event_draft_404_kecuali_admin(client):
    fx = make_fanmeet()
    fx.event.status = EventStatus.DRAFT
    fx.event.save()
    assert client.get(f"/event/{fx.event.slug}/").status_code == 404
    admin = get_user_model().objects.create_superuser("own", "o@x.id", "rahasia-panjang-1")
    client.force_login(admin)
    response = client.get(f"/event/{fx.event.slug}/")
    assert response.status_code == 200 and "Pratinjau" in response.content.decode()


def test_tahap_tutup_form_tidak_bisa_dibuka(client):
    fx = make_fanmeet()
    fx.phase.status = PhaseStatus.TUTUP
    fx.phase.save()
    response = client.get(f"/event/{fx.event.slug}/pesan/")
    assert response.status_code == 302 and response["Location"] == f"/event/{fx.event.slug}/"


# --- Form pesanan ---------------------------------------------------------------

def test_pesanan_contoh4_dua_baris_dan_halaman_sukses(client):
    fx = make_fanmeet()
    response = order_post(client, fx, jaswar_line(fx, 0, 2, CONTOH4[0]), jastip_line(fx, 1, 1, CONTOH4[1]))
    order = Order.objects.get()
    assert response.status_code == 302 and response["Location"] == f"/pesanan/{order.code}/berhasil/"
    assert order.status == OrderStatus.MENUNGGU_FEE
    assert TicketSlot.objects.filter(line__order=order).count() == 3
    assert order.buyer_instagram == "rinaputri"
    jastip = order.lines.get(service_type="JASTIP")
    assert jastip.holder_nik == "" and jastip.holder_email == ""

    html = client.get(response["Location"]).content.decode()
    assert order.code in html
    assert "Rp 750.000" in html  # tagihan sekarang
    assert "Rp 9.500.000" in html  # pelunasan nanti
    assert "Rp 10.250.000" in html  # bayar sekaligus
    assert NIK not in html and "•••• •••• •••• 8901" in html


def test_kategori_sama_ditolak(client):
    fx = make_fanmeet()
    response = order_post(client, fx, jaswar_line(fx, 0, 1, ("CAT 1", "CAT 1", "CAT 2")))
    assert response.status_code == 200 and Order.objects.count() == 0
    html = response.content.decode()
    assert "harus berbeda" in html
    assert 'data-initial-step="2"' in html  # kembali ke langkah tiket
    assert NIK not in html  # NIK tidak dirender ulang


def test_jaswar_wajib_lengkap_jastip_minimal(client):
    fx = make_fanmeet()
    bad = jaswar_line(fx, 0, 1, CONTOH4[0])
    bad.update({"lines-0-holder_nik": "123", "lines-0-holder_birth_date": "", "lines-0-holder_instagram": ""})
    html = order_post(client, fx, bad).content.decode()
    assert "16 digit" in html and "Tanggal lahir wajib" in html and "Username IG wajib" in html
    assert Order.objects.count() == 0
    response = order_post(client, fx, jastip_line(fx, 0, 1, CONTOH4[1]), method="VA_BCA")
    assert response.status_code == 302 and Order.objects.count() == 1


def test_kuota_penuh_masuk_waiting_list(client):
    fx = make_fanmeet(slot_quota=1)
    order_post(client, fx, jaswar_line(fx, 0, 2, CONTOH4[0]))
    order = Order.objects.get()
    assert order.status == OrderStatus.WAITING_LIST
    html = client.get(f"/pesanan/{order.code}/berhasil/").content.decode()
    assert "waiting list" in html and "belum perlu bayar" in html


def test_rate_limit_lima_pesanan_per_sepuluh_menit(client):
    fx = make_fanmeet()
    for n in range(5):
        response = order_post(client, fx, jastip_line(fx, 0, 1, CONTOH4[1], name=f"P{n}"), method="VA_BCA")
        assert response.status_code == 302
    response = order_post(client, fx, jastip_line(fx, 0, 1, CONTOH4[1]), method="VA_BCA")
    assert response.status_code == 200 and "Terlalu banyak pesanan" in response.content.decode()
    assert Order.objects.count() == 5


def test_honeypot_tidak_membuat_pesanan(client):
    fx = make_fanmeet()
    response = order_post(client, fx, jastip_line(fx, 0, 1, CONTOH4[1]), website="http://spam")
    assert response.status_code == 302 and Order.objects.count() == 0


def test_kirim_ganda_tidak_membuat_pesanan_kedua(client):
    fx = make_fanmeet()
    token = token_of(client, fx)
    first = order_post(client, fx, jastip_line(fx, 0, 1, CONTOH4[1]), token=token)
    second = order_post(client, fx, jastip_line(fx, 0, 1, CONTOH4[1]), token=token)
    assert Order.objects.count() == 1
    assert first["Location"] == second["Location"]


def test_halaman_sukses_hanya_untuk_pemesan_atau_token(client):
    fx = make_fanmeet()
    order_post(client, fx, jastip_line(fx, 0, 1, CONTOH4[1]))
    order = Order.objects.get()
    stranger = Client()
    assert stranger.get(f"/pesanan/{order.code}/berhasil/").status_code == 404
    assert stranger.get(f"/pesanan/{order.code}/berhasil/?t={make_tracking_token(order)}").status_code == 200


def test_ringkasan_live_dari_pricing(client):
    fx = make_fanmeet()
    data = {"phase": fx.phase.pk, "pay-payment_method": "TITIP_BAYAR"}
    data.update(jaswar_line(fx, 0, 2, CONTOH4[0]))
    data.update(jastip_line(fx, 1, 1, CONTOH4[1]))
    html = client.post(f"/event/{fx.event.slug}/pesan/hitung/", data).content.decode()
    assert "Rp 750.000" in html and "Rp 9.500.000" in html
    assert 'id="bar-total"' in html and 'hx-swap-oob="true"' in html
    # Data setengah jadi tidak membuat error
    html = client.post(f"/event/{fx.event.slug}/pesan/hitung/",
                       {"phase": fx.phase.pk, "lines-0-service_type": "JASWAR"}).content.decode()
    assert "pilih kategori" in html


def test_form_tanpa_script_inline(client):
    fx = make_fanmeet()
    html = client.get(f"/event/{fx.event.slug}/pesan/").content.decode()
    assert "<script>" not in html and " onclick=" not in html
    assert html.count('class="line-card card"') == fx.event.max_lines_per_order
