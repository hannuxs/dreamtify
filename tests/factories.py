"""Factory sederhana untuk tes. Data contoh = docs/02 §4.5 (event fanmeet)."""
from dataclasses import dataclass
from datetime import date, timedelta
from itertools import count

from django.utils import timezone

from apps.core.actors import Actor
from apps.core.enums import (
    EventStatus,
    FeeTier,
    PhaseStatus,
    ServiceType,
    SlotResult,
    TicketPaymentMethod,
)
from apps.events.models import Event, FeeRule, SalePhase, TicketCategory
from apps.orders.models import Order, TicketSlot
from apps.orders.services import transitions
from apps.orders.services.validation import BuyerData, HolderData, LineData

_seq = count(1)

CUSTOMER = Actor(label="customer tes", kind="customer")
SYSTEM = Actor.system()

JASWAR = ServiceType.JASWAR
JASTIP = ServiceType.JASTIP
TITIP = TicketPaymentMethod.TITIP_BAYAR
VA_BCA = TicketPaymentMethod.VA_BCA


@dataclass
class Fanmeet:
    event: Event
    phase: SalePhase
    cats: dict  # nama → TicketCategory

    def cat(self, name):
        return self.cats[name]


def make_fanmeet(*, slot_quota=None, war_in=timedelta(days=3), **event_kw) -> Fanmeet:
    """Contoh fanmeet docs/02 §4.5: Duality 3,5jt (VIP), CAT 1–3 (REGULER), fee Presale."""
    n = next(_seq)
    now = timezone.now()
    event = Event.objects.create(
        name=f"Contoh Fanmeet {n}", slug=f"contoh-fanmeet-{n}", status=EventStatus.TAMPIL,
        first_show_date=(now + timedelta(days=30)).date(), **event_kw,
    )
    phase = SalePhase.objects.create(
        event=event, name="Presale", status=PhaseStatus.BUKA,
        order_open_at=now - timedelta(days=1), order_close_at=now + war_in - timedelta(hours=3),
        war_at=now + war_in, pelunasan_deadline=now + war_in - timedelta(days=1),
        slot_quota=slot_quota,
    )
    cats = {}
    for i, (name, tier, price) in enumerate([
        ("Duality Package", FeeTier.VIP, 3_500_000),
        ("CAT 1", FeeTier.REGULER, 2_500_000),
        ("CAT 2", FeeTier.REGULER, 2_000_000),
        ("CAT 3", FeeTier.REGULER, 1_500_000),
    ]):
        cats[name] = TicketCategory.objects.create(event=event, name=name, fee_tier=tier, price=price, sort_order=i)
    for service, tier, fee in [
        (JASWAR, FeeTier.VIP, 250_000), (JASWAR, FeeTier.REGULER, 200_000),
        (JASTIP, FeeTier.VIP, 300_000), (JASTIP, FeeTier.REGULER, 250_000),
    ]:
        FeeRule.objects.create(phase=phase, service_type=service, fee_tier=tier, fee_per_ticket=fee)
    return Fanmeet(event=event, phase=phase, cats=cats)


def buyer(**kw) -> BuyerData:
    data = dict(name="Rina Putri", whatsapp="0812-3456-7890", email="rina@example.com", instagram="@rinaputri")
    data.update(kw)
    return BuyerData(**data)


def jaswar_holder(name="Rina Putri", nik="3171012345678901", **kw) -> HolderData:
    data = dict(name=name, nik=nik, gender="P", birth_date=date(2000, 5, 17), email="rina@example.com",
                whatsapp="081234567890", instagram="rinaputri")
    data.update(kw)
    return HolderData(**data)


def jastip_holder(name="Dodi", whatsapp="081298765432", **kw) -> HolderData:
    return HolderData(name=name, whatsapp=whatsapp, **kw)


def line(fx: Fanmeet, service, qty, cats=("Duality Package", "CAT 1", "CAT 2"), holder=None) -> LineData:
    ids = [fx.cat(c).pk if c else None for c in cats] + [None, None]
    if holder is None:
        holder = jaswar_holder() if service == JASWAR else jastip_holder()
    return LineData(service_type=service, quantity=qty, primary=ids[0], backup1=ids[1], backup2=ids[2],
                    holder=holder)


def make_order(fx: Fanmeet, lines, method=TITIP, **kw) -> Order:
    return transitions.create_order(phase=fx.phase, buyer=kw.pop("buyer_data", buyer()), lines=lines,
                                    payment_method=method, actor=CUSTOMER, **kw)


def pay(order, amount, admin, *, received=None):
    """Customer kirim bukti + admin verifikasi."""
    payment = transitions.submit_payment(order, amount=amount, actor=admin, sender_name="Rina")
    transitions.verify_payment(payment, actor=admin, amount_received=received)
    order.refresh_from_db()
    return payment


def slots(order) -> list:
    return list(TicketSlot.objects.filter(line__order=order).select_related("line").order_by("line__sort_order", "index"))


def set_results(order, admin, *results):
    """results: tuple (SlotResult, nama kategori|None) per tiket, urut baris → tiket."""
    phase_order = slots(order)
    assert len(phase_order) == len(results)
    fx_cats = {c.name: c for c in order.event.categories.all()}
    for slot, (result, cat) in zip(phase_order, results):
        transitions.set_slot_result(slot, result, actor=admin, category=fx_cats[cat] if cat else None)
    order.refresh_from_db()


SECURED = SlotResult.SECURED
GAGAL = SlotResult.GAGAL
GAGAL_CUSTOMER = SlotResult.GAGAL_CUSTOMER
