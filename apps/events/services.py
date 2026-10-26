"""
Logika event: publikasi, duplikat, token promotor, status tahap.
Dipanggil view dashboard & halaman publik (bukan dihitung di template).
"""
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from apps.core import audit
from apps.core.actors import Actor
from apps.core.enums import EventStatus, PhaseStatus, ServiceType, TicketPaymentMethod

from .models import Event, FeeRule, SalePhase, TicketCategory, new_promotor_token

PUBLIC_EVENT_STATUSES = (EventStatus.TAMPIL, EventStatus.SELESAI)


# ---------------------------------------------------------------------------
# Publikasi
# ---------------------------------------------------------------------------

def phase_problems(event, phase, *, categories=None, fees=None) -> list[str]:
    """Apa yang kurang agar tahap ini boleh BUKA (docs/05 §2 validasi publikasi)."""
    problems = []
    cats = categories if categories is not None else list(event.categories.filter(is_active=True))
    if not cats:
        problems.append("Belum ada kategori tiket aktif.")
    if not event.enabled_services():
        problems.append("Belum ada layanan (JASWAR/JASTIP) yang aktif.")
    if not event.payment_methods:
        problems.append("Belum ada metode bayar tiket yang aktif.")
    if not phase.war_at:
        problems.append(f"{phase.name}: waktu war belum diisi.")
    rules = fees if fees is not None else {(r.service_type, r.fee_tier) for r in phase.fee_rules.all()}
    tiers = sorted({c.fee_tier for c in cats})
    missing = [f"{s} {t}" for s in event.enabled_services() for t in tiers if (s, t) not in rules]
    if missing:
        problems.append(f"{phase.name}: matriks fee belum lengkap ({', '.join(missing)}).")
    return problems


def publication_problems(event, *, phases=None) -> list[str]:
    """Masalah yang membuat event TAMPIL + tahap BUKA tidak boleh disimpan.
    `phases`: tahap yang akan berstatus BUKA (default: dari DB)."""
    if phases is None:
        phases = list(event.phases.filter(status=PhaseStatus.BUKA).prefetch_related("fee_rules"))
    cats = list(event.categories.filter(is_active=True))
    problems = []
    for phase in phases:
        for problem in phase_problems(event, phase, categories=cats):
            if problem not in problems:
                problems.append(problem)
    return problems


def checklist(event) -> list[tuple[str, bool]]:
    """Daftar cek untuk panel 'Siap publikasi' di form event."""
    phases = list(event.phases.prefetch_related("fee_rules"))
    cats = list(event.categories.filter(is_active=True))
    fee_ok = bool(phases) and all(
        not [p for p in phase_problems(event, ph, categories=cats) if "matriks fee" in p] for ph in phases)
    return [
        ("Info event (nama, tanggal, venue)", bool(event.name and event.event_dates and event.venue)),
        ("Minimal satu tahap penjualan", bool(phases)),
        ("Kategori tiket aktif", bool(cats)),
        ("Matriks fee lengkap untuk setiap tahap", fee_ok),
        ("Waktu war setiap tahap", bool(phases) and all(p.war_at for p in phases)),
        ("Layanan & metode bayar aktif", bool(event.enabled_services() and event.payment_methods)),
    ]


# ---------------------------------------------------------------------------
# Tahap terbuka untuk publik
# ---------------------------------------------------------------------------

def phase_accepts_orders(event, phase, now=None) -> bool:
    now = now or timezone.now()
    return (
        event.status == EventStatus.TAMPIL
        and phase.status == PhaseStatus.BUKA
        and (phase.order_open_at is None or phase.order_open_at <= now)
        and (phase.order_close_at is None or now < phase.order_close_at)
    )


def visible_phases(event) -> list:
    return [p for p in event.phases.all() if p.status != PhaseStatus.DRAFT]


def open_phases(event, now=None) -> list:
    return [p for p in event.phases.all() if phase_accepts_orders(event, p, now)]


# ---------------------------------------------------------------------------
# Slug, duplikat, token
# ---------------------------------------------------------------------------

def unique_slug(name: str, *, exclude_pk=None) -> str:
    base = slugify(name)[:150] or "event"
    slug, n = base, 2
    while Event.objects.filter(slug=slug).exclude(pk=exclude_pk).exists():
        slug = f"{base}-{n}"
        n += 1
    return slug


@transaction.atomic
def duplicate_event(event: Event, *, actor: Actor) -> Event:
    """Salin event + tahap + kategori + matriks fee (tanpa pesanan).
    Nama "(salinan)", status DRAFT, tanggal dikosongkan, token promotor baru."""
    source_pk = event.pk
    copy = Event.objects.get(pk=source_pk)
    copy.pk = None
    copy.name = f"{event.name} (salinan)"[:150]
    copy.slug = unique_slug(copy.name)
    copy.status = EventStatus.DRAFT
    copy.event_dates = ""
    copy.first_show_date = None
    copy.promotor_token = new_promotor_token()
    copy.promotor_link_enabled = False
    copy.created_by = actor.user
    copy.save()

    for cat in TicketCategory.objects.filter(event_id=source_pk):
        cat.pk = None
        cat.event = copy
        cat.save()
    for phase in SalePhase.objects.filter(event_id=source_pk).prefetch_related("fee_rules"):
        rules = list(phase.fee_rules.all())
        phase.pk = None
        phase.event = copy
        phase.status = PhaseStatus.DRAFT
        phase.order_open_at = phase.order_close_at = phase.war_at = phase.pelunasan_deadline = None
        phase.war_started_at = phase.war_finished_at = None
        phase.save()
        FeeRule.objects.bulk_create([
            FeeRule(phase=phase, service_type=r.service_type, fee_tier=r.fee_tier, fee_per_ticket=r.fee_per_ticket)
            for r in rules
        ])
    audit.log("event.duplicate", actor=actor, obj=copy, summary=f"Duplikat dari {event.name}",
              data={"source": source_pk})
    return copy


def regenerate_promotor_token(event: Event, *, actor: Actor) -> Event:
    event.promotor_token = new_promotor_token()
    event.save(update_fields=["promotor_token", "updated_at"])
    audit.log("event.promotor_token", actor=actor, obj=event, summary="Link promotor diganti (link lama mati)")
    return event


def copy_fee_matrix(source: SalePhase, target: SalePhase, *, actor: Actor) -> int:
    count = 0
    for rule in source.fee_rules.all():
        FeeRule.objects.update_or_create(phase=target, service_type=rule.service_type, fee_tier=rule.fee_tier,
                                         defaults={"fee_per_ticket": rule.fee_per_ticket})
        count += 1
    audit.log("event.fee_copy", actor=actor, obj=target.event,
              summary=f"Matriks fee {source.name} disalin ke {target.name}")
    return count


PAYMENT_METHOD_HINTS = {
    TicketPaymentMethod.VA_BCA: "Kamu bayar sendiri saat war lewat VA. Wajib standby. "
                                "Telat bayar = tiket hangus & fee tidak kembali.",
    TicketPaymentMethod.VA_MANDIRI: "Kamu bayar sendiri saat war lewat VA. Wajib standby. "
                                    "Telat bayar = tiket hangus & fee tidak kembali.",
    TicketPaymentMethod.TITIP_BAYAR: "Kamu titip uang harga tiket ke kami (tidak perlu standby). "
                                     "Nominal = kategori termahal pilihanmu × jumlah; selisih dikembalikan setelah war.",
}

SERVICE_HINTS = {
    ServiceType.JASWAR: "Jasa war saja. Pakai data kamu. Gelang kamu tukar sendiri.",
    ServiceType.JASTIP: "Terima beres. Pakai data tim. Gelang kami tukarkan & serahkan.",
}
