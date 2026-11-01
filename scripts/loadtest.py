"""Uji beban ringan (hanya dev): 50 pesanan lewat form, beberapa thread, kuota tidak boleh jebol.

Pemakaian: .venv\\Scripts\\python scripts\\loadtest.py [jumlah] [kuota]

Memakai django.test.Client agar seluruh tumpukan (form, validasi, transaksi, kuota) terpakai tanpa
perlu server, tiap thread dengan IP sendiri supaya tidak terkena rate limit form. Membuat event
sementara lalu menghapusnya kembali.
"""
import os
import re
import sys
import threading
import time
import uuid
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_ENV", "dev")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.dev")
if os.environ["DJANGO_ENV"] != "dev":
    sys.exit("loadtest hanya untuk DJANGO_ENV=dev.")

import django  # noqa: E402

django.setup()

from django.conf import settings  # noqa: E402
from django.db import connection  # noqa: E402
from django.test import Client  # noqa: E402
from django.utils import timezone  # noqa: E402

from apps.core.enums import EventStatus, FeeTier, OrderStatus, PhaseStatus, ServiceType  # noqa: E402
from apps.events.models import Event, FeeRule, SalePhase, TicketCategory  # noqa: E402
from apps.orders.models import Order  # noqa: E402
from apps.orders.services import quota  # noqa: E402

WORKERS = 5


def make_event(ticket_quota):
    slug = f"uji-beban-{uuid.uuid4().hex[:8]}"
    now = timezone.now()
    event = Event.objects.create(name="Uji Beban", slug=slug, status=EventStatus.TAMPIL,
                                 first_show_date=(now + timedelta(days=30)).date())
    phase = SalePhase.objects.create(event=event, name="Presale", status=PhaseStatus.BUKA, slot_quota=ticket_quota,
                                     order_open_at=now - timedelta(days=1), order_close_at=now + timedelta(days=2),
                                     war_at=now + timedelta(days=3), pelunasan_deadline=now + timedelta(days=2))
    cats = [TicketCategory.objects.create(event=event, name=name, price=1_000_000, fee_tier=FeeTier.REGULER, sort_order=i)
            for i, name in enumerate(("CAT 1", "CAT 2", "CAT 3"))]
    FeeRule.objects.create(phase=phase, service_type=ServiceType.JASTIP, fee_tier=FeeTier.REGULER, fee_per_ticket=200_000)
    return event, phase, cats


def place(event, phase, cats, index, results):
    client = Client(REMOTE_ADDR=f"10.9.{index // 200}.{index % 200 + 1}")
    html = client.get(f"/event/{event.slug}/pesan/?tahap={phase.pk}").content.decode()
    token = re.search(r'name="form_token" value="([^"]+)"', html).group(1)
    response = client.post(f"/event/{event.slug}/pesan/", {
        "phase": phase.pk, "form_token": token, "buyer-name": f"Beban {index}", "buyer-whatsapp": f"08129{index:07d}",
        "buyer-email": f"beban{index}@contoh.test", "buyer-instagram": f"beban{index}", "pay-payment_method": "TITIP_BAYAR",
        "agree-agree_terms": "on", "agree-agree_privacy": "on", "lines-0-service_type": "JASTIP", "lines-0-quantity": "1",
        "lines-0-primary": cats[0].pk, "lines-0-backup1": cats[1].pk, "lines-0-backup2": cats[2].pk,
        "lines-0-holder_name": f"Beban {index}", "lines-0-holder_whatsapp": f"08129{index:07d}"})
    results.append(response.status_code)


def main():
    total = int(sys.argv[1]) if len(sys.argv) > 1 else 50
    ticket_quota = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    settings.ALLOWED_HOSTS = ["*"]
    event, phase, cats = make_event(ticket_quota)
    results, errors, pending = [], [], list(range(total))
    lock = threading.Lock()

    def worker():
        while True:
            with lock:
                if not pending:
                    break
                index = pending.pop()
            try:
                place(event, phase, cats, index, results)
            except Exception as exc:  # dilaporkan di akhir
                errors.append(repr(exc))
        connection.close()

    started = time.perf_counter()
    threads = [threading.Thread(target=worker) for _ in range(WORKERS)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    elapsed = time.perf_counter() - started

    orders = Order.objects.filter(event=event)
    used = quota.used_tickets(phase)
    waiting = orders.filter(status=OrderStatus.WAITING_LIST).count()
    print(f"{total} kiriman dalam {elapsed:.1f} dtk ({total / elapsed * 60:.0f}/menit), {WORKERS} thread")
    print(f"Pesanan: {orders.count()}, memakai kuota: {used}/{ticket_quota}, waiting list: {waiting}")
    print(f"HTTP: { {code: results.count(code) for code in set(results)} }, error: {len(errors)}")
    ok = not errors and used <= ticket_quota and orders.count() == total and used + waiting == total
    orders.delete()
    event.delete()
    if errors:
        print("Contoh error:", errors[0][:300])
    print("LULUS" if ok else "GAGAL")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
