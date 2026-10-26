import secrets

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.enums import (
    EventStatus,
    FeeBasis,
    FeeTier,
    LatePelunasanPolicy,
    PhaseStatus,
    ServiceType,
    TicketPaymentMethod,
)
from apps.core.models import TimeStampedModel
from apps.core.uploads import public_upload_to


def new_promotor_token() -> str:
    return secrets.token_urlsafe(24)  # 32 karakter


def default_payment_methods() -> list:
    return [m.value for m in TicketPaymentMethod]


class Event(TimeStampedModel):
    name = models.CharField("nama event", max_length=150)
    slug = models.SlugField(max_length=160, unique=True)
    artist = models.CharField("artis", max_length=150, blank=True)
    venue = models.CharField(max_length=150, blank=True)
    city = models.CharField("kota", max_length=80, blank=True)
    event_dates = models.CharField("tanggal (teks)", max_length=100, blank=True,
                                   help_text='Teks bebas, mis. "29–30 Okt 2026"')
    first_show_date = models.DateField("tanggal pertama", null=True, blank=True, db_index=True)
    poster = models.ImageField(upload_to=public_upload_to, blank=True)
    description = models.TextField("deskripsi", blank=True)
    ticketing_platform = models.CharField("platform tiket", max_length=80, blank=True)
    status = models.CharField(max_length=12, choices=EventStatus.choices,
                              default=EventStatus.DRAFT, db_index=True)

    # --- Aturan ---
    jaswar_enabled = models.BooleanField("JASWAR aktif", default=True)
    jastip_enabled = models.BooleanField("JASTIP aktif", default=True)
    payment_methods = models.JSONField("metode bayar tiket", default=default_payment_methods,
                                       help_text="Daftar nilai TicketPaymentMethod")
    max_lines_per_order = models.PositiveSmallIntegerField(
        "maks baris tiket per pesanan", default=6, validators=[MinValueValidator(1), MaxValueValidator(20)])
    max_tickets_per_holder = models.PositiveSmallIntegerField(
        "maks tiket per pemegang", default=4, validators=[MinValueValidator(1), MaxValueValidator(4)])
    required_backups = models.PositiveSmallIntegerField(
        "jumlah cadangan wajib", default=2, validators=[MaxValueValidator(2)])
    fee_basis = models.CharField("dasar fee", max_length=16, choices=FeeBasis.choices,
                                 default=FeeBasis.TIER_TERTINGGI)
    booking_slot_fee = models.PositiveBigIntegerField("booking slot (Rp/tiket)", default=50000)
    early_booking_per_ticket = models.PositiveBigIntegerField(
        "early booking (Rp/tiket)", default=0, help_text="0 = tidak ada. Hanya untuk Titip Bayar.")
    fee_payment_window_hours = models.PositiveSmallIntegerField(
        "jendela bayar fee (jam)", default=24, validators=[MinValueValidator(1)])
    late_pelunasan_policy = models.CharField(
        "kebijakan lewat batas pelunasan", max_length=24,
        choices=LatePelunasanPolicy.choices, default=LatePelunasanPolicy.HANGUS)
    unique_code_enabled = models.BooleanField("kode unik nominal", default=False)
    customer_va_enabled = models.BooleanField("customer boleh kirim VA war mandiri", default=True)
    fallback_any_category = models.BooleanField(
        "boleh amankan kategori apa pun bila pilihan habis", default=True)
    terms = models.TextField("syarat khusus event", blank=True)
    redemption_info = models.TextField("info penukaran gelang (JASWAR)", blank=True)

    # --- Promotor ---
    promotor_name = models.CharField("nama promotor", max_length=120, blank=True)
    promotor_token = models.CharField(max_length=64, unique=True, default=new_promotor_token)
    promotor_link_enabled = models.BooleanField("link promotor aktif", default=False)
    promotor_include_nik = models.BooleanField("sertakan NIK di ekspor promotor", default=False)

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-first_show_date", "-id"]
        verbose_name = "event"
        verbose_name_plural = "event"

    def __str__(self):
        return self.name

    def enabled_services(self) -> list[str]:
        services = []
        if self.jaswar_enabled:
            services.append(ServiceType.JASWAR.value)
        if self.jastip_enabled:
            services.append(ServiceType.JASTIP.value)
        return services


class SalePhase(TimeStampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="phases")
    name = models.CharField("nama tahap", max_length=60, help_text='"Presale", "Gensale"')
    sort_order = models.PositiveSmallIntegerField("urutan", default=0)
    status = models.CharField(max_length=10, choices=PhaseStatus.choices,
                              default=PhaseStatus.DRAFT, db_index=True)
    order_open_at = models.DateTimeField("pesanan dibuka", null=True, blank=True)
    order_close_at = models.DateTimeField("pesanan ditutup", null=True, blank=True)
    war_at = models.DateTimeField("waktu war", null=True, blank=True)
    pelunasan_deadline = models.DateTimeField("batas pelunasan", null=True, blank=True)
    slot_quota = models.PositiveIntegerField("kuota slot (tiket)", null=True, blank=True,
                                             help_text="Kosong = tanpa batas")
    membership_required = models.BooleanField("wajib membership", default=False)
    membership_label = models.CharField(max_length=150, blank=True,
                                        default="No Membership (wajib sudah registrasi presale)")
    war_started_at = models.DateTimeField(null=True, blank=True)
    war_finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "tahap penjualan"
        verbose_name_plural = "tahap penjualan"
        constraints = [models.UniqueConstraint(fields=["event", "name"], name="uniq_phase_name")]

    def __str__(self):
        return f"{self.event} – {self.name}"


class TicketCategory(TimeStampedModel):
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="categories")
    name = models.CharField("nama kategori", max_length=80)
    fee_tier = models.CharField("tier fee", max_length=8, choices=FeeTier.choices, default=FeeTier.REGULER)
    price = models.PositiveBigIntegerField("harga tiket (Rp)")
    sort_order = models.PositiveSmallIntegerField("urutan", default=0)
    is_active = models.BooleanField("aktif", default=True)
    description = models.CharField("keterangan", max_length=150, blank=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "kategori tiket"
        verbose_name_plural = "kategori tiket"
        constraints = [models.UniqueConstraint(fields=["event", "name"], name="uniq_category_name")]

    def __str__(self):
        return self.name


class FeeRule(TimeStampedModel):
    phase = models.ForeignKey(SalePhase, on_delete=models.CASCADE, related_name="fee_rules")
    service_type = models.CharField("layanan", max_length=8, choices=ServiceType.choices)
    fee_tier = models.CharField("tier", max_length=8, choices=FeeTier.choices)
    fee_per_ticket = models.PositiveBigIntegerField("fee per tiket (Rp)")

    class Meta:
        verbose_name = "aturan fee"
        verbose_name_plural = "matriks fee"
        constraints = [
            models.UniqueConstraint(fields=["phase", "service_type", "fee_tier"], name="uniq_fee_rule"),
        ]

    def __str__(self):
        return f"{self.phase} {self.service_type} {self.fee_tier}: {self.fee_per_ticket}"
