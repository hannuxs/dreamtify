"""
Rumus harga saat pesanan dibuat — docs/02 §4.1.

Fungsi di sini MURNI (tanpa query) agar bisa dipakai untuk pratinjau form
(ringkasan biaya live) maupun saat menyimpan pesanan. Data event/tahap
dikumpulkan sekali ke `PricingContext`, yang juga disimpan sebagai
`Order.pricing_snapshot` sehingga hasil war dihitung dengan angka yang
berlaku saat memesan.

Notasi baris L: q = jumlah tiket, s = layanan, C = kategori pilihan.
    tier_dasar      = tier tertinggi di C (TIER_TERTINGGI) / tier kategori utama
    fee_awal        = q × fee(tahap, s, tier_dasar)
    harga_dasar     = q × max(harga(c) untuk c di C)
    early_booking   = q × early_booking_per_ticket   (hanya TITIP_BAYAR)
    TAGIHAN_AWAL      = Σ fee_awal + Σ early_booking − potongan_kode_unik
    TAGIHAN_PELUNASAN = Σ harga_dasar − Σ early_booking   (hanya TITIP_BAYAR)
"""
from dataclasses import dataclass

from apps.core.enums import TIER_RANK, FeeBasis, FeeTier, TicketPaymentMethod


class PricingError(ValueError):
    """Data harga tidak lengkap (mis. sel matriks fee kosong)."""


@dataclass(frozen=True)
class CategoryInfo:
    id: int
    name: str
    tier: str
    price: int
    is_active: bool = True


@dataclass(frozen=True)
class PricingContext:
    categories: dict  # id -> CategoryInfo
    fees: dict  # (service_type, tier) -> fee per tiket
    fee_basis: str = FeeBasis.TIER_TERTINGGI
    booking_slot_fee: int = 50000
    early_booking_per_ticket: int = 0

    def fee(self, service_type: str, tier: str) -> int:
        try:
            return self.fees[(str(service_type), str(tier))]
        except KeyError:
            raise PricingError(f"Fee untuk {service_type} {tier} belum diatur di tahap ini.") from None

    def category(self, category_id: int) -> CategoryInfo:
        try:
            return self.categories[int(category_id)]
        except (KeyError, TypeError, ValueError):
            raise PricingError("Kategori tidak dikenal untuk event ini.") from None

    # --- Snapshot (JSON) ---
    def to_snapshot(self) -> dict:
        return {
            "categories": {
                str(c.id): {"name": c.name, "tier": c.tier, "price": c.price, "active": c.is_active}
                for c in self.categories.values()
            },
            "fees": {f"{s}:{t}": v for (s, t), v in self.fees.items()},
            "fee_basis": self.fee_basis,
            "booking_slot_fee": self.booking_slot_fee,
            "early_booking_per_ticket": self.early_booking_per_ticket,
        }

    @classmethod
    def from_snapshot(cls, data: dict) -> "PricingContext":
        categories = {
            int(cid): CategoryInfo(int(cid), c["name"], c["tier"], int(c["price"]), c.get("active", True))
            for cid, c in data.get("categories", {}).items()
        }
        fees = {}
        for key, value in data.get("fees", {}).items():
            service, tier = key.split(":", 1)
            fees[(service, tier)] = int(value)
        return cls(
            categories=categories,
            fees=fees,
            fee_basis=data.get("fee_basis", FeeBasis.TIER_TERTINGGI),
            booking_slot_fee=int(data.get("booking_slot_fee", 0)),
            early_booking_per_ticket=int(data.get("early_booking_per_ticket", 0)),
        )

    @classmethod
    def for_phase(cls, phase) -> "PricingContext":
        """Kumpulkan harga dari DB (2 query)."""
        event = phase.event
        categories = {
            c.id: CategoryInfo(c.id, c.name, c.fee_tier, c.price, c.is_active)
            for c in event.categories.all()
        }
        fees = {(r.service_type, r.fee_tier): r.fee_per_ticket for r in phase.fee_rules.all()}
        return cls(
            categories=categories,
            fees=fees,
            fee_basis=event.fee_basis,
            booking_slot_fee=event.booking_slot_fee,
            early_booking_per_ticket=event.early_booking_per_ticket,
        )


@dataclass(frozen=True)
class LineInput:
    service_type: str
    quantity: int
    category_ids: tuple  # (utama, cadangan1, cadangan2) — None dilewati


@dataclass(frozen=True)
class LineQuote:
    service_type: str
    quantity: int
    tier: str
    fee_per_ticket: int
    price_basis_per_ticket: int
    early_booking_per_ticket: int

    @property
    def fee_total(self) -> int:
        return self.quantity * self.fee_per_ticket

    @property
    def price_total(self) -> int:
        return self.quantity * self.price_basis_per_ticket

    @property
    def early_total(self) -> int:
        return self.quantity * self.early_booking_per_ticket


@dataclass(frozen=True)
class OrderQuote:
    lines: tuple
    payment_method: str
    unique_discount: int = 0

    @property
    def is_titip_bayar(self) -> bool:
        return self.payment_method == TicketPaymentMethod.TITIP_BAYAR

    @property
    def total_tickets(self) -> int:
        return sum(line.quantity for line in self.lines)

    @property
    def fee_total(self) -> int:
        return sum(line.fee_total for line in self.lines)

    @property
    def early_total(self) -> int:
        return sum(line.early_total for line in self.lines)

    @property
    def price_total(self) -> int:
        return sum(line.price_total for line in self.lines)

    @property
    def initial_due(self) -> int:
        """TAGIHAN_AWAL"""
        return max(0, self.fee_total + self.early_total - self.unique_discount)

    @property
    def pelunasan_due(self) -> int:
        """TAGIHAN_PELUNASAN (0 untuk metode VA)"""
        if not self.is_titip_bayar:
            return 0
        return max(0, self.price_total - self.early_total)

    @property
    def total_before_war(self) -> int:
        return self.initial_due + self.pelunasan_due


def highest_tier(tiers) -> str:
    return max(tiers, key=lambda t: TIER_RANK[FeeTier(t)])


def quote_line(ctx: PricingContext, line: LineInput, payment_method: str) -> LineQuote:
    ids = [cid for cid in line.category_ids if cid]
    if not ids:
        raise PricingError("Kategori utama wajib dipilih.")
    if int(line.quantity) < 1:
        raise PricingError("Jumlah tiket minimal 1.")
    cats = [ctx.category(cid) for cid in ids]
    if ctx.fee_basis == FeeBasis.KATEGORI_UTAMA:
        tier = cats[0].tier
    else:
        tier = highest_tier(c.tier for c in cats)
    early = ctx.early_booking_per_ticket if payment_method == TicketPaymentMethod.TITIP_BAYAR else 0
    return LineQuote(
        service_type=str(line.service_type),
        quantity=int(line.quantity),
        tier=str(tier),
        fee_per_ticket=ctx.fee(line.service_type, tier),
        price_basis_per_ticket=max(c.price for c in cats),
        early_booking_per_ticket=early,
    )


def quote_order(ctx: PricingContext, lines, payment_method: str, unique_discount: int = 0) -> OrderQuote:
    return OrderQuote(
        lines=tuple(quote_line(ctx, line, payment_method) for line in lines),
        payment_method=str(payment_method),
        unique_discount=int(unique_discount or 0),
    )


def quote_saved_order(order) -> OrderQuote:
    """Rangkum tagihan dari snapshot baris pesanan yang tersimpan (tanpa hitung ulang harga)."""
    return OrderQuote(
        lines=tuple(
            LineQuote(
                service_type=line.service_type,
                quantity=line.quantity,
                tier=line.tier_snapshot,
                fee_per_ticket=line.fee_per_ticket_snapshot,
                price_basis_per_ticket=line.price_basis_per_ticket_snapshot,
                early_booking_per_ticket=line.early_booking_per_ticket_snapshot,
            )
            for line in order.lines.all()
        ),
        payment_method=order.ticket_payment_method,
        unique_discount=order.unique_discount,
    )


def order_context(order) -> PricingContext:
    """Konteks harga sebuah pesanan: dari snapshot, atau dari DB bila snapshot kosong."""
    if order.pricing_snapshot:
        return PricingContext.from_snapshot(order.pricing_snapshot)
    return PricingContext.for_phase(order.phase)
