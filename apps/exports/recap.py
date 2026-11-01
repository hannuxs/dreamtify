"""Rekap angka (tanpa data pribadi) untuk layar admin, sheet `Rekap`, dan halaman promotor."""
from dataclasses import dataclass, field

from apps.core.enums import SlotResult, TicketPaymentMethod
from apps.core.models import AuditLog

EXPORT_ACTION = "export.promotor"


@dataclass
class Recap:
    categories: list = field(default_factory=list)  # {name, orders, requested, secured}
    services: list = field(default_factory=list)  # {name, orders, tickets, secured}
    methods: list = field(default_factory=list)  # {name, orders, tickets}
    orders: int = 0
    tickets: int = 0
    secured: int = 0


def build(lines, categories) -> Recap:
    """lines: OrderLine (dengan order, slots). categories: kategori event sesuai urutan tampil."""
    cats = {c.pk: {"name": c.name, "orders": set(), "requested": 0, "secured": 0} for c in categories}
    services, methods = {}, {}
    all_orders, tickets, secured = set(), 0, 0
    for line in lines:
        order = line.order
        all_orders.add(order.pk)
        tickets += line.quantity
        cats[line.cat_primary_id]["orders"].add(order.pk)
        cats[line.cat_primary_id]["requested"] += line.quantity
        got = [s for s in line.slots.all() if s.result == SlotResult.SECURED]
        secured += len(got)
        for slot in got:
            cats[slot.secured_category_id]["secured"] += 1
        service = services.setdefault(line.service_type, {"name": line.service_type, "orders": set(), "tickets": 0,
                                                          "secured": 0})
        service["orders"].add(order.pk)
        service["tickets"] += line.quantity
        service["secured"] += len(got)
        label = TicketPaymentMethod(order.ticket_payment_method).label
        method = methods.setdefault(label, {"name": label, "orders": set(), "tickets": 0})
        method["orders"].add(order.pk)
        method["tickets"] += line.quantity

    def counted(row):
        return {**row, "orders": len(row["orders"])}

    return Recap(categories=[counted(r) for r in cats.values() if r["requested"] or r["secured"]],
                 services=[counted(services[k]) for k in sorted(services)],
                 methods=[counted(methods[k]) for k in sorted(methods)],
                 orders=len(all_orders), tickets=tickets, secured=secured)


def download_stats(event) -> dict:
    """Statistik unduhan untuk tab Promotor (dari AuditLog)."""
    logs = AuditLog.objects.filter(action=EXPORT_ACTION, object_type="events.event", object_id=str(event.pk))
    return {"total": logs.count(), "last": logs.first(), "via_link": logs.filter(data__via="link").count()}
