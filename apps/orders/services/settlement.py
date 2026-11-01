"""
Penyelesaian keuangan — docs/02 §4.3 (hasil war) & §4.4 (pembatalan).

    dibayar        = Σ Payment masuk (FEE/PELUNASAN/KEKURANGAN) DITERIMA
    TAGIHAN_FINAL  = Σ fee_final + Σ harga_final − potongan_kode_unik
    SALDO          = dibayar − Σ REFUND DITERIMA − TAGIHAN_FINAL
                     > 0 → hak refund, < 0 → kekurangan bayar

Per tiket:
    MENUNGGU (belum ada hasil) → fee_awal + harga_dasar (titip bayar)
                                  = tagihan sebelum war, sehingga SALDO sebelum
                                  war = dibayar − TOTAL_SEBELUM_WAR
    SECURED kategori c         → fee(s, tier(c)) + harga(c) (titip bayar)
    GAGAL                      → min(booking_slot, fee_awal)
    GAGAL_CUSTOMER             → fee_awal (tidak direfund)

Semua fungsi membaca relasi lewat `.all()` sehingga memakai prefetch bila ada.
"""
from dataclasses import dataclass

from apps.core.enums import (
    INCOMING_PAYMENT_KINDS,
    CancelReason,
    LatePelunasanPolicy,
    OrderStatus,
    PaymentKind,
    PaymentStatus,
    SlotResult,
    TicketPaymentMethod,
)

from .pricing import CategoryInfo, PricingError, order_context, quote_saved_order


# ---------------------------------------------------------------------------
# Pembayaran
# ---------------------------------------------------------------------------

def paid_in(order) -> int:
    return sum(
        p.amount_received or 0
        for p in order.payments.all()
        if p.kind in INCOMING_PAYMENT_KINDS and p.status == PaymentStatus.DITERIMA
    )


def refunded(order) -> int:
    return sum(
        p.amount_received or 0
        for p in order.payments.all()
        if p.kind == PaymentKind.REFUND and p.status == PaymentStatus.DITERIMA
    )


def pending_incoming(order) -> list:
    return [
        p for p in order.payments.all()
        if p.kind in INCOMING_PAYMENT_KINDS and p.status == PaymentStatus.MENUNGGU
    ]


def has_money(order) -> bool:
    """Sudah ada uang masuk, atau bukti masuk yang sedang dicek."""
    return paid_in(order) > 0 or bool(pending_incoming(order))


# ---------------------------------------------------------------------------
# Hasil war
# ---------------------------------------------------------------------------

def _secured_info(ctx, slot) -> CategoryInfo:
    try:
        return ctx.category(slot.secured_category_id)
    except PricingError:
        # Kategori dibuat setelah pesanan: pakai data kategori saat ini
        c = slot.secured_category
        return CategoryInfo(c.id, c.name, c.fee_tier, c.price, c.is_active)


def slot_final(ctx, line, slot, payment_method) -> tuple[int, int]:
    """(fee_final, harga_final) satu tiket."""
    titip = payment_method == TicketPaymentMethod.TITIP_BAYAR
    fee_awal = line.fee_per_ticket_snapshot
    if slot.result == SlotResult.SECURED:
        cat = _secured_info(ctx, slot)
        return ctx.fee(line.service_type, cat.tier), (cat.price if titip else 0)
    if slot.result == SlotResult.GAGAL:
        return min(ctx.booking_slot_fee, fee_awal), 0
    if slot.result == SlotResult.GAGAL_CUSTOMER:
        return fee_awal, 0
    # MENUNGGU: belum ada hasil → tagihan sebelum war
    return fee_awal, (line.price_basis_per_ticket_snapshot if titip else 0)


def all_results_in(order) -> bool:
    slots = [s for line in order.lines.all() for s in line.slots.all()]
    return bool(slots) and all(s.result != SlotResult.MENUNGGU for s in slots)


def war_totals(order) -> tuple[int, int]:
    """(Σ fee_final, Σ harga_final) berdasarkan hasil per tiket."""
    ctx = order_context(order)
    fee_sum = price_sum = 0
    for line in order.lines.all():
        for slot in line.slots.all():
            fee, price = slot_final(ctx, line, slot, order.ticket_payment_method)
            fee_sum += fee
            price_sum += price
    return fee_sum, price_sum


# ---------------------------------------------------------------------------
# Pembatalan (§4.4)
# ---------------------------------------------------------------------------

def cancellation_final_due(order, status: str, reason: str) -> int:
    """TAGIHAN_FINAL bila pesanan berakhir dengan status & alasan ini.

    ASUMSI: setiap nilai dibatasi `min(dibayar, …)` agar pembatalan tidak pernah
    membuat customer berutang. Early booking ikut hangus (ASUMSI D2).
    """
    if reason in (CancelReason.BATAL_ADMIN, CancelReason.EVENT_BATAL, CancelReason.LEWAT_BATAS_FEE):
        return 0
    paid = paid_in(order)
    quote = quote_saved_order(order)
    if status == OrderStatus.HANGUS:
        return min(paid, quote.initial_due)
    if reason == CancelReason.LEWAT_BATAS_PELUNASAN:  # DIBATALKAN, kebijakan refund − booking
        return min(paid, quote.total_tickets * order_context(order).booking_slot_fee)
    return 0  # DIBATALKAN + BATAL_CUSTOMER sebelum ada uang


def cancel_status_for(order, reason: str) -> str:
    """Status akhir bila pesanan dibatalkan dengan alasan ini."""
    if reason == CancelReason.BATAL_CUSTOMER:
        if order.status == OrderStatus.WAITING_LIST or not has_money(order):
            return OrderStatus.DIBATALKAN
        return OrderStatus.HANGUS
    if reason == CancelReason.LEWAT_BATAS_PELUNASAN:
        if order.event.late_pelunasan_policy == LatePelunasanPolicy.HANGUS:
            return OrderStatus.HANGUS
        return OrderStatus.DIBATALKAN
    return OrderStatus.DIBATALKAN


@dataclass(frozen=True)
class CancellationPreview:
    status: str
    reason: str
    paid: int
    final_due: int  # yang ditahan Dreamtify (hangus)
    refund: int  # yang dikembalikan ke customer

    @property
    def forfeited(self) -> int:
        return self.final_due


def cancellation_preview(order, reason: str = CancelReason.BATAL_CUSTOMER) -> CancellationPreview:
    """Untuk dialog batal: berapa yang hangus & berapa yang kembali."""
    status = cancel_status_for(order, reason)
    final = cancellation_final_due(order, status, reason)
    paid = paid_in(order)
    return CancellationPreview(
        status=status,
        reason=reason,
        paid=paid,
        final_due=final,
        refund=max(0, paid - refunded(order) - final),
    )


# ---------------------------------------------------------------------------
# Ringkasan
# ---------------------------------------------------------------------------

def final_due(order) -> int:
    if order.status in (OrderStatus.DIBATALKAN, OrderStatus.HANGUS):
        return cancellation_final_due(order, order.status, order.cancel_reason)
    fee_sum, price_sum = war_totals(order)
    return max(0, fee_sum + price_sum - order.unique_discount)


def balance(order) -> int:
    return paid_in(order) - refunded(order) - final_due(order)


@dataclass(frozen=True)
class Summary:
    initial_due: int  # TAGIHAN_AWAL
    pelunasan_due: int  # TAGIHAN_PELUNASAN
    total_before_war: int
    paid_in: int
    refunded: int
    pending_in: int  # nominal klaim bukti yang sedang dicek
    final_due: int  # TAGIHAN_FINAL
    balance: int  # SALDO
    results_final: bool  # semua tiket sudah punya hasil (atau pesanan batal)

    @property
    def refund_due(self) -> int:
        return max(0, self.balance)

    @property
    def shortfall(self) -> int:
        return max(0, -self.balance)

    @property
    def remaining_before_war(self) -> int:
        """Sisa yang harus dibayar sebelum war (0 bila sudah lunas)."""
        return max(0, self.total_before_war - self.paid_in)

    @property
    def remaining_initial(self) -> int:
        return max(0, self.initial_due - self.paid_in)


def summarize(order) -> Summary:
    quote = quote_saved_order(order)
    paid = paid_in(order)
    ref = refunded(order)
    final = final_due(order)
    cancelled = order.status in (OrderStatus.DIBATALKAN, OrderStatus.HANGUS)
    return Summary(
        initial_due=quote.initial_due,
        pelunasan_due=quote.pelunasan_due,
        total_before_war=quote.total_before_war,
        paid_in=paid,
        refunded=ref,
        pending_in=sum(p.amount_claimed for p in pending_incoming(order)),
        final_due=final,
        balance=paid - ref - final,
        results_final=cancelled or all_results_in(order),
    )


# ---------------------------------------------------------------------------
# Rekap keuangan (docs/05 §10)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class OrderFinance:
    order: object
    summary: Summary
    fee_income: int  # pendapatan fee final (0 bila belum final)
    ticket_price: int  # harga tiket final titip bayar (0 bila belum final)
    held: int  # uang customer yang masih dipegang


@dataclass
class FinanceRecap:
    fee_received: int = 0
    pelunasan_received: int = 0  # termasuk pembayaran kekurangan
    refund_out: int = 0
    held: int = 0  # hak refund belum ditransfer + seluruh uang pesanan yang belum final
    shortfall: int = 0
    fee_income: int = 0  # Σ fee_final pesanan yang sudah final
    ticket_price: int = 0  # Σ harga tiket final (titip bayar)

    @property
    def money_in(self) -> int:
        return self.fee_received + self.pelunasan_received


def order_finance(order) -> OrderFinance:
    """ASUMSI: pesanan belum final (belum semua hasil masuk) belum menghasilkan pendapatan;
    seluruh uangnya dihitung tertahan. Bagian hangus pesanan batal = pendapatan."""
    summary = summarize(order)
    if not summary.results_final:
        return OrderFinance(order, summary, 0, 0, summary.paid_in - summary.refunded)
    cancelled = order.status in (OrderStatus.DIBATALKAN, OrderStatus.HANGUS)
    price = 0 if cancelled else war_totals(order)[1]
    return OrderFinance(order, summary, summary.final_due - price, price, summary.refund_due)


def finance_recap(orders) -> tuple[FinanceRecap, list]:
    """(rekap, [OrderFinance]). Selalu: masuk − refund = fee + harga tiket + tertahan − kekurangan."""
    recap = FinanceRecap()
    rows = []
    for order in orders:
        row = order_finance(order)
        rows.append(row)
        # ASUMSI: customer boleh bayar sekaligus (satu Payment jenis FEE), jadi porsi fee dihitung dari
        # tagihan awal, bukan dari jenis pembayaran; sisanya pelunasan/kekurangan.
        fee_part = min(row.summary.paid_in, row.summary.initial_due)
        recap.fee_received += fee_part
        recap.pelunasan_received += row.summary.paid_in - fee_part
        recap.refund_out += row.summary.refunded
        recap.held += row.held
        recap.fee_income += row.fee_income
        recap.ticket_price += row.ticket_price
        if row.summary.results_final:
            recap.shortfall += row.summary.shortfall
    return recap, rows
