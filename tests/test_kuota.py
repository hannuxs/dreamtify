"""Kuota & waiting list (docs/02 §6) — termasuk dua pesanan bersamaan."""
import threading
import time

import pytest
from django.db import connections

from apps.core.enums import OrderStatus
from apps.orders.models import Order
from apps.orders.services import quota

from .factories import JASWAR, buyer, jaswar_holder, line, make_fanmeet, make_order


@pytest.mark.django_db(transaction=True)
def test_dua_pesanan_bersamaan_untuk_sisa_kuota_satu(monkeypatch):
    fx = make_fanmeet(slot_quota=1)
    original = quota.used_tickets

    def slow_used_tickets(phase):
        value = original(phase)
        time.sleep(0.4)  # perlebar jendela balapan: tanpa kunci, keduanya akan lolos
        return value

    monkeypatch.setattr(quota, "used_tickets", slow_used_tickets)
    barrier = threading.Barrier(2)
    errors = []

    def worker(n):
        try:
            barrier.wait()
            make_order(fx, [line(fx, JASWAR, 1, holder=jaswar_holder(nik=f"317101000000000{n}"))],
                       buyer_data=buyer(name=f"Pemesan {n}"))
        except Exception as exc:  # pragma: no cover - dilaporkan di assert
            errors.append(exc)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=worker, args=(n,)) for n in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    statuses = sorted(Order.objects.filter(phase=fx.phase).values_list("status", flat=True))
    assert statuses == sorted([OrderStatus.MENUNGGU_FEE, OrderStatus.WAITING_LIST])


@pytest.mark.django_db
def test_hitung_kuota_dan_sisa():
    fx = make_fanmeet(slot_quota=5)
    assert quota.remaining(fx.phase) == 5
    make_order(fx, [line(fx, JASWAR, 3)])
    assert quota.used_tickets(fx.phase) == 3
    assert quota.can_fit(fx.phase, 2) and not quota.can_fit(fx.phase, 3)
    b = make_order(fx, [line(fx, JASWAR, 3, holder=jaswar_holder(nik="3171019999999999"))],
                   buyer_data=buyer(name="Budi"))
    assert b.status == OrderStatus.WAITING_LIST  # semua-atau-tidak
    assert quota.used_tickets(fx.phase) == 3  # waiting list tidak memakai kuota


@pytest.mark.django_db
def test_tanpa_kuota_tidak_terbatas():
    fx = make_fanmeet(slot_quota=None)
    assert quota.remaining(fx.phase) is None
    assert make_order(fx, [line(fx, JASWAR, 4)]).status == OrderStatus.MENUNGGU_FEE
