"""seed_initial idempoten, grup & izin, template, dan Django admin di /kelola/sistem/."""
import re

import pytest
from django.contrib import admin as django_admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command

from apps.core.models import BankAccount, FaqItem, SiteSetting
from apps.notifications.defaults import DEFAULT_TEMPLATES
from apps.notifications.models import MessageTemplate
from apps.notifications.services import build_context, render
from apps.orders.models import OrderLine

from .factories import JASWAR, line, make_order

pytestmark = pytest.mark.django_db


def test_seed_initial_idempoten():
    call_command("seed_initial", verbosity=0)
    call_command("seed_initial", verbosity=0)
    assert SiteSetting.objects.count() == 1
    assert BankAccount.objects.filter(account_number="7805519240").count() == 1
    assert FaqItem.objects.count() == 9
    assert MessageTemplate.objects.count() == len(DEFAULT_TEMPLATES) == 20
    owner, admin = Group.objects.get(name="Owner"), Group.objects.get(name="Admin")
    assert owner.permissions.filter(codename="view_full_nik").exists()
    assert not admin.permissions.filter(codename="view_full_nik").exists()
    assert not admin.permissions.filter(codename="change_sitesetting").exists()
    assert admin.permissions.filter(codename="change_order").exists()


def test_seed_tidak_menimpa_template_yang_diubah():
    call_command("seed_initial", verbosity=0)
    MessageTemplate.objects.filter(key="FEE_DITERIMA").update(body="Versi Owner {kode}", is_customized=True)
    call_command("seed_initial", verbosity=0)
    assert MessageTemplate.objects.get(key="FEE_DITERIMA").body == "Versi Owner {kode}"


def test_semua_template_default_terender_tanpa_placeholder_tersisa(fanmeet):
    order = make_order(fanmeet, [line(fanmeet, JASWAR, 1)])
    ctx = build_context(order)
    for key, (_, body, _) in DEFAULT_TEMPLATES.items():
        text = render(body, ctx)
        assert not re.search(r"\{[a-z_]+\}", text), key
        assert order.code in text and "/lacak/" + order.code in text, key


@pytest.fixture
def superuser_client(client):
    user = get_user_model().objects.create_superuser("owner", "o@example.com", "rahasia-panjang-1")
    client.force_login(user)
    return client


def test_admin_menampilkan_semua_model(superuser_client, fanmeet):
    make_order(fanmeet, [line(fanmeet, JASWAR, 1)])
    for model, model_admin in django_admin.site._registry.items():
        if model._meta.app_label not in ("core", "events", "orders", "notifications", "testimonials"):
            continue
        url = f"/kelola/sistem/{model._meta.app_label}/{model._meta.model_name}/"
        assert superuser_client.get(url).status_code == 200, url


def test_admin_nik_tersamar(superuser_client, fanmeet):
    order = make_order(fanmeet, [line(fanmeet, JASWAR, 1)])
    ln = OrderLine.objects.get(order=order)
    for url in (f"/kelola/sistem/orders/orderline/{ln.pk}/change/",
                f"/kelola/sistem/orders/order/{order.pk}/change/"):
        html = superuser_client.get(url).content.decode()
        assert "3171012345678901" not in html
        assert "8901" in html


def test_admin_hanya_superuser(client, admin_user):
    client.force_login(admin_user)  # staff biasa, bukan superuser
    response = client.get("/kelola/sistem/")
    assert response.status_code == 302 and "/login/" in response["Location"]
