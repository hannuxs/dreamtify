"""Rumus §4.1 sebagai fungsi murni + FeeBasis, early booking, kode unik."""
import pytest

from apps.core.enums import FeeBasis, FeeTier, OrderStatus
from apps.orders.selectors import get_order
from apps.orders.services import settlement, transitions
from apps.orders.services.pricing import (
    CategoryInfo,
    LineInput,
    PricingContext,
    PricingError,
    quote_order,
)

from .factories import (
    GAGAL,
    JASTIP,
    JASWAR,
    SECURED,
    TITIP,
    VA_BCA,
    buyer,
    line,
    make_fanmeet,
    make_order,
    pay,
    set_results,
)

DUALITY, CAT1, CAT2, CAT3 = 1, 2, 3, 4


def ctx(**kw):
    data = dict(
        categories={
            DUALITY: CategoryInfo(DUALITY, "Duality Package", FeeTier.VIP, 3_500_000),
            CAT1: CategoryInfo(CAT1, "CAT 1", FeeTier.REGULER, 2_500_000),
            CAT2: CategoryInfo(CAT2, "CAT 2", FeeTier.REGULER, 2_000_000),
            CAT3: CategoryInfo(CAT3, "CAT 3", FeeTier.REGULER, 1_500_000),
        },
        fees={("JASWAR", "VIP"): 250_000, ("JASWAR", "REGULER"): 200_000,
              ("JASTIP", "VIP"): 300_000, ("JASTIP", "REGULER"): 250_000},
        booking_slot_fee=50_000,
    )
    data.update(kw)
    return PricingContext(**data)


# --- Fungsi murni -----------------------------------------------------------

def test_quote_contoh4_murni():
    q = quote_order(ctx(), [LineInput("JASWAR", 2, (DUALITY, CAT1, CAT2)),
                            LineInput("JASTIP", 1, (CAT3, CAT2, CAT1))], TITIP)
    assert (q.initial_due, q.pelunasan_due, q.total_before_war) == (750_000, 9_500_000, 10_250_000)
    assert q.lines[1].tier == FeeTier.REGULER and q.lines[1].price_basis_per_ticket == 2_500_000


def test_va_tidak_ada_pelunasan():
    q = quote_order(ctx(), [LineInput("JASWAR", 2, (DUALITY, CAT1, CAT2))], VA_BCA)
    assert (q.initial_due, q.pelunasan_due) == (500_000, 0)


def test_fee_basis_tier_tertinggi_vs_kategori_utama():
    lines = [LineInput("JASWAR", 1, (CAT1, DUALITY, CAT2))]  # utama Reguler, cadangan VIP
    assert quote_order(ctx(), lines, TITIP).initial_due == 250_000
    utama = quote_order(ctx(fee_basis=FeeBasis.KATEGORI_UTAMA), lines, TITIP)
    assert utama.initial_due == 200_000
    assert utama.lines[0].tier == FeeTier.REGULER
    # Harga dasar tetap kategori termahal di antara pilihan
    assert utama.pelunasan_due == 3_500_000


def test_early_booking_hanya_titip_bayar():
    c = ctx(early_booking_per_ticket=100_000)
    titip = quote_order(c, [LineInput("JASWAR", 2, (DUALITY, CAT1, CAT2))], TITIP)
    assert titip.initial_due == 500_000 + 200_000
    assert titip.pelunasan_due == 7_000_000 - 200_000
    assert titip.total_before_war == 7_500_000  # total tidak berubah, hanya dimajukan
    va = quote_order(c, [LineInput("JASWAR", 2, (DUALITY, CAT1, CAT2))], VA_BCA)
    assert va.initial_due == 500_000


def test_kode_unik_mengurangi_tagihan_awal():
    q = quote_order(ctx(), [LineInput("JASWAR", 1, (CAT3, CAT2, CAT1))], TITIP, unique_discount=123)
    assert q.initial_due == 200_000 - 123


def test_fee_belum_diatur_error():
    c = ctx(fees={("JASWAR", "REGULER"): 200_000})
    with pytest.raises(PricingError):
        quote_order(c, [LineInput("JASWAR", 1, (DUALITY,))], TITIP)


def test_snapshot_bolak_balik():
    c = ctx(early_booking_per_ticket=10_000)
    assert PricingContext.from_snapshot(c.to_snapshot()) == c


# --- Dengan pesanan tersimpan -------------------------------------------------

@pytest.mark.django_db
@pytest.mark.parametrize("hasil, refund", [
    ((GAGAL, GAGAL), 7_400_000),  # early booking ikut direfund
    ((SECURED, SECURED), 1_050_000),  # early booking tidak dihitung dua kali
])
def test_early_booking_tidak_dihitung_dua_kali(admin, hasil, refund):
    fx = make_fanmeet(early_booking_per_ticket=100_000)
    order = make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))])
    assert (order.fee_due, order.pelunasan_due) == (700_000, 6_800_000)
    pay(order, 700_000, admin)
    pay(order, 6_800_000, admin)
    assert order.status == OrderStatus.SIAP_WAR
    transitions.start_war(fx.phase, actor=admin)
    cats = ("Duality Package", "CAT 1")
    set_results(order, admin, *[(r, cats[i] if r == SECURED else None) for i, r in enumerate(hasil)])
    assert settlement.summarize(get_order(order.code)).balance == refund


@pytest.mark.django_db
def test_kode_unik_pada_pesanan(admin):
    fx = make_fanmeet(unique_code_enabled=True)
    a = make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))])
    b = make_order(fx, [line(fx, JASWAR, 2, ("Duality Package", "CAT 1", "CAT 2"))],
                   buyer_data=buyer(name="Budi"))
    assert 1 <= a.unique_code <= 499
    assert a.unique_code != b.unique_code
    assert a.fee_due == 500_000 - a.unique_code
    # Setelah war, potongan kode unik tetap diperhitungkan di TAGIHAN_FINAL
    pay(a, a.fee_due, admin)
    pay(a, a.pelunasan_due, admin)
    transitions.start_war(fx.phase, actor=admin)
    set_results(a, admin, (SECURED, "Duality Package"), (SECURED, "CAT 1"))
    s = settlement.summarize(get_order(a.code))
    assert s.final_due == 6_450_000 - a.unique_code
    assert s.balance == 1_050_000


@pytest.mark.django_db
def test_snapshot_harga_tidak_ikut_berubah(admin):
    """Perubahan harga event setelah pesanan dibuat tidak mengubah pesanan lama."""
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 1, ("CAT 3", "CAT 2", "CAT 1"))])
    pay(order, 200_000, admin)
    pay(order, 2_500_000, admin)
    fx.cat("Duality Package").price = 9_000_000
    fx.cat("Duality Package").save()
    fx.phase.fee_rules.update(fee_per_ticket=999_000)
    transitions.start_war(fx.phase, actor=admin)
    set_results(order, admin, (SECURED, "Duality Package"))
    assert settlement.summarize(get_order(order.code)).final_due == 3_750_000


@pytest.mark.django_db
def test_jastip_vip_fee(admin):
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASTIP, 1, ("Duality Package", "CAT 1", "CAT 2"))], method=VA_BCA)
    assert order.fee_due == 300_000
