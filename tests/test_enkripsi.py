"""Enkripsi NIK & rekening (docs/09 §1–2)."""
import json

import pytest
from cryptography.fernet import Fernet
from django.db import connection

from apps.core import crypto
from apps.core.models import AuditLog
from apps.notifications.models import Notification
from apps.orders.models import Order, OrderLine

from .factories import JASWAR, jaswar_holder, line, make_order

pytestmark = pytest.mark.django_db
NIK = "3171012345678901"


def raw(sql, params):
    with connection.cursor() as cursor:
        cursor.execute(sql, params)
        return cursor.fetchone()[0]


def test_nik_terenkripsi_di_database(fanmeet):
    order = make_order(fanmeet, [line(fanmeet, JASWAR, 1, holder=jaswar_holder(nik="3171 0123 4567 8901"))])
    ln = OrderLine.objects.get(order=order)
    stored = raw(f"SELECT holder_nik FROM {OrderLine._meta.db_table} WHERE id = %s", [ln.pk])
    assert NIK not in stored and stored.startswith("gAAAA")  # token Fernet
    assert ln.holder_nik == NIK  # didekripsi otomatis
    assert ln.holder_nik_last4 == "8901"
    assert ln.nik_masked == "•••• •••• •••• 8901"
    assert ln.holder_nik_hash == crypto.nik_hash(NIK) == crypto.nik_hash("3171-0123-4567-8901")
    assert crypto.nik_hash(NIK) != crypto.nik_hash("3171012345678902")


def test_rekening_refund_terenkripsi(fanmeet):
    order = make_order(fanmeet, [line(fanmeet, JASWAR, 1)])
    order.refund_account_number = "1234567890"
    order.save()
    stored = raw(f"SELECT refund_account_number FROM {Order._meta.db_table} WHERE id = %s", [order.pk])
    assert "1234567890" not in stored
    assert Order.objects.get(pk=order.pk).refund_account_number == "1234567890"
    assert order.refund_account_masked == "••••••7890"


def test_rotasi_kunci(settings):
    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()
    settings.FIELD_ENCRYPTION_KEYS = [old]
    token = crypto.encrypt_str(NIK)
    settings.FIELD_ENCRYPTION_KEYS = [new, old]  # kunci baru di depan, lama tetap bisa dekripsi
    assert crypto.decrypt_str(token) == NIK
    assert crypto.decrypt_str(crypto.encrypt_str(NIK)) == NIK
    settings.FIELD_ENCRYPTION_KEYS = [new]
    with pytest.raises(crypto.DecryptionError):
        crypto.decrypt_str(token)


def test_nik_tidak_bocor_ke_audit_dan_kabar(fanmeet, admin):
    order = make_order(fanmeet, [line(fanmeet, JASWAR, 1)])
    order.refund_account_number = "9876543210"
    order.save()
    from .factories import pay
    pay(order, 200_000, admin)
    for log in AuditLog.objects.all():
        assert NIK not in log.summary and NIK not in json.dumps(log.data)
    for n in Notification.objects.all():
        assert NIK not in n.rendered_text and "9876543210" not in n.rendered_text
    # NIK juga tidak ada di snapshot harga / kolom teks lain pesanan
    assert NIK not in json.dumps(Order.objects.filter(pk=order.pk).values().get(), default=str)
