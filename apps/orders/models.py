"""
Model pesanan. Model hanya menyimpan data; semua rumus & perubahan status ada
di `apps/orders/services/` (CLAUDE.md §6.2–6.3).
"""
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import F, Q

from apps.core.crypto import EncryptedTextField, mask_account, mask_nik
from apps.core.enums import (
    CancelReason,
    FeeTier,
    FulfillmentStatus,
    Gender,
    HandoverMethod,
    OrderStatus,
    PaymentKind,
    PaymentStatus,
    ServiceType,
    SlotResult,
    SubmittedVia,
    TicketPaymentMethod,
    VaSource,
    VaStatus,
)
from apps.core.models import BankAccount, TimeStampedModel
from apps.core.uploads import private_upload_to
from apps.events.models import Event, SalePhase, TicketCategory


class Order(TimeStampedModel):
    code = models.CharField("kode", max_length=12, unique=True)
    event = models.ForeignKey(Event, on_delete=models.PROTECT, related_name="orders")
    phase = models.ForeignKey(SalePhase, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=24, choices=OrderStatus.choices, db_index=True)
    cancel_reason = models.CharField("alasan batal", max_length=24, choices=CancelReason.choices,
                                     null=True, blank=True)
    ticket_payment_method = models.CharField("metode bayar tiket", max_length=12,
                                             choices=TicketPaymentMethod.choices)

    # --- Pemesan ---
    buyer_name = models.CharField("nama pemesan", max_length=150)
    buyer_whatsapp = models.CharField("WA pemesan", max_length=20, db_index=True, help_text="Format 62…")
    buyer_email = models.EmailField("email pemesan")
    buyer_instagram = models.CharField("IG pemesan", max_length=64, blank=True)
    referral = models.CharField("perekomendasi (WA/IG)", max_length=150, blank=True)
    customer_note = models.TextField("catatan customer", blank=True)
    admin_note = models.TextField("catatan internal", blank=True)

    # --- Snapshot tagihan (docs/02 §4.1) ---
    fee_due = models.PositiveBigIntegerField(
        "tagihan awal", default=0,
        help_text="TAGIHAN_AWAL = Σ fee awal + Σ early booking − potongan kode unik")
    pelunasan_due = models.PositiveBigIntegerField(
        "tagihan pelunasan", default=0, help_text="Σ harga dasar − Σ early booking (Titip Bayar)")
    unique_discount = models.PositiveIntegerField("potongan kode unik", default=0)
    unique_code = models.PositiveSmallIntegerField("kode unik", null=True, blank=True)
    # ASUMSI: seluruh tabel fee, harga kategori & booking slot saat pesanan dibuat
    # disimpan agar hasil war (termasuk kategori di luar pilihan) dihitung dengan
    # angka yang berlaku saat memesan, bukan harga event terbaru.
    pricing_snapshot = models.JSONField("snapshot harga", default=dict, blank=True)

    fee_deadline = models.DateTimeField("batas bayar fee", null=True, blank=True, db_index=True)
    agreed_terms_at = models.DateTimeField("setuju syarat", null=True, blank=True)

    # --- Refund ---
    refund_bank_name = models.CharField("bank refund", max_length=50, blank=True)
    refund_account_holder = models.CharField("atas nama refund", max_length=120, blank=True)
    refund_account_number = EncryptedTextField("no. rekening refund", blank=True)

    # --- Lain-lain ---
    last_customer_view_at = models.DateTimeField(null=True, blank=True)
    is_late_pelunasan = models.BooleanField("lewat batas pelunasan", default=False, db_index=True)
    has_duplicate_nik_warning = models.BooleanField("peringatan NIK ganda", default=False)
    source_ip = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "pesanan"
        verbose_name_plural = "pesanan"
        indexes = [models.Index(fields=["phase", "status"], name="order_phase_status_idx")]

    def __str__(self):
        return self.code

    @property
    def refund_account_masked(self) -> str:
        return mask_account(self.refund_account_number)


class OrderLine(TimeStampedModel):
    """Satu baris tiket = satu isian Google Form lama (1 pemegang)."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="lines")
    sort_order = models.PositiveSmallIntegerField(default=0)
    service_type = models.CharField("layanan", max_length=8, choices=ServiceType.choices)
    quantity = models.PositiveSmallIntegerField(
        "jumlah tiket", validators=[MinValueValidator(1), MaxValueValidator(4)])
    cat_primary = models.ForeignKey(TicketCategory, on_delete=models.PROTECT, related_name="+",
                                    verbose_name="kategori utama")
    cat_backup1 = models.ForeignKey(TicketCategory, on_delete=models.PROTECT, related_name="+",
                                    null=True, blank=True, verbose_name="cadangan 1")
    cat_backup2 = models.ForeignKey(TicketCategory, on_delete=models.PROTECT, related_name="+",
                                    null=True, blank=True, verbose_name="cadangan 2")

    # --- Pemegang tiket ---
    holder_name = models.CharField("nama pemegang", max_length=150)
    holder_nik = EncryptedTextField("NIK", blank=True)
    holder_nik_hash = models.CharField(max_length=64, blank=True, db_index=True)
    holder_nik_last4 = models.CharField(max_length=4, blank=True)
    holder_gender = models.CharField("jenis kelamin", max_length=1, choices=Gender.choices, blank=True)
    holder_birth_date = models.DateField("tanggal lahir", null=True, blank=True)
    holder_email = models.EmailField("email pemegang", blank=True)
    holder_whatsapp = models.CharField("WA pemegang", max_length=20, blank=True)
    holder_instagram = models.CharField("IG pemegang", max_length=64, blank=True)
    holder_membership_no = models.CharField("no. membership", max_length=64, blank=True)
    same_as_buyer = models.BooleanField("sama dengan pemesan", default=False)

    # --- Snapshot harga per tiket (docs/02 §4.1) ---
    tier_snapshot = models.CharField(max_length=8, choices=FeeTier.choices)
    fee_per_ticket_snapshot = models.PositiveBigIntegerField()
    price_basis_per_ticket_snapshot = models.PositiveBigIntegerField()
    early_booking_per_ticket_snapshot = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "baris tiket"
        verbose_name_plural = "baris tiket"
        permissions = [("view_full_nik", "Bisa melihat NIK penuh")]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gte=1) & Q(quantity__lte=4),
                                   name="line_quantity_1_4"),
            models.CheckConstraint(condition=~Q(cat_primary=F("cat_backup1")),
                                   name="line_primary_ne_backup1"),
            models.CheckConstraint(condition=~Q(cat_primary=F("cat_backup2")),
                                   name="line_primary_ne_backup2"),
            models.CheckConstraint(condition=~Q(cat_backup1=F("cat_backup2")),
                                   name="line_backup1_ne_backup2"),
        ]

    def __str__(self):
        return f"{self.order.code} #{self.sort_order + 1} {self.holder_name}"

    def clean(self):
        chosen = [c for c in (self.cat_primary_id, self.cat_backup1_id, self.cat_backup2_id) if c]
        if len(chosen) != len(set(chosen)):
            raise ValidationError("Kategori utama, cadangan 1, dan cadangan 2 harus berbeda.")

    @property
    def category_ids(self) -> list[int]:
        return [c for c in (self.cat_primary_id, self.cat_backup1_id, self.cat_backup2_id) if c]

    @property
    def nik_masked(self) -> str:
        return mask_nik(self.holder_nik_last4)


class TicketSlot(TimeStampedModel):
    """Satu tiket fisik/elektronik: hasil war & penyerahan."""

    line = models.ForeignKey(OrderLine, on_delete=models.CASCADE, related_name="slots")
    index = models.PositiveSmallIntegerField("tiket ke-")
    result = models.CharField("hasil", max_length=16, choices=SlotResult.choices,
                              default=SlotResult.MENUNGGU, db_index=True)
    secured_category = models.ForeignKey(TicketCategory, on_delete=models.PROTECT, null=True, blank=True,
                                         related_name="+", verbose_name="kategori didapat")
    ticket_reference = models.CharField("kode tiket / booking", max_length=100, blank=True)
    result_set_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                      on_delete=models.SET_NULL, related_name="+")
    result_set_at = models.DateTimeField(null=True, blank=True)

    fulfillment_status = models.CharField("status penyerahan", max_length=16,
                                          choices=FulfillmentStatus.choices,
                                          default=FulfillmentStatus.MENUNGGU, db_index=True)
    handover_method = models.CharField("metode penyerahan", max_length=16,
                                       choices=HandoverMethod.choices, blank=True)
    handover_detail = models.TextField("detail penyerahan", blank=True)
    handover_receiver_name = models.CharField("nama penerima", max_length=150, blank=True)
    handover_photo = models.FileField("foto penyerahan", upload_to=private_upload_to, blank=True)
    eticket_file = models.FileField("e-tiket", upload_to=private_upload_to, blank=True)
    fulfillment_note = models.TextField("catatan untuk customer", blank=True)
    fulfillment_updated_at = models.DateTimeField(null=True, blank=True)
    # Penanda versi untuk deteksi konflik antar-admin di Mode War
    version = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["line_id", "index"]
        verbose_name = "tiket"
        verbose_name_plural = "tiket"
        constraints = [models.UniqueConstraint(fields=["line", "index"], name="uniq_slot_index")]

    def __str__(self):
        return f"{self.line.order.code} tiket {self.index}"


class Payment(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="payments")
    kind = models.CharField("jenis", max_length=12, choices=PaymentKind.choices)
    status = models.CharField(max_length=10, choices=PaymentStatus.choices,
                              default=PaymentStatus.MENUNGGU, db_index=True)
    amount_claimed = models.PositiveBigIntegerField("nominal (klaim)")
    amount_received = models.PositiveBigIntegerField(
        "nominal diterima", null=True, blank=True, help_text="Untuk REFUND = nominal yang ditransfer")
    sender_name = models.CharField("nama pengirim", max_length=150, blank=True)
    sender_bank = models.CharField("bank pengirim", max_length=50, blank=True)
    transfer_date = models.DateField("tanggal transfer", null=True, blank=True)
    proof = models.FileField("bukti", upload_to=private_upload_to, blank=True)
    destination_account = models.ForeignKey(BankAccount, null=True, blank=True, on_delete=models.SET_NULL,
                                            related_name="+", verbose_name="rekening tujuan")
    reject_reason = models.TextField("alasan ditolak", blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    verified_at = models.DateTimeField(null=True, blank=True)
    submitted_via = models.CharField(max_length=10, choices=SubmittedVia.choices,
                                     default=SubmittedVia.CUSTOMER)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "pembayaran"
        verbose_name_plural = "pembayaran"
        indexes = [models.Index(fields=["order", "kind", "status"], name="payment_order_kind_idx")]

    def __str__(self):
        return f"{self.order.code} {self.kind} {self.amount_claimed}"


class VaNotice(TimeStampedModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="va_notices")
    source = models.CharField("sumber", max_length=10, choices=VaSource.choices, default=VaSource.ADMIN)
    bank = models.CharField(max_length=50)
    va_number = models.CharField("nomor VA", max_length=64)
    amount = models.PositiveBigIntegerField("nominal")
    expires_at = models.DateTimeField("batas bayar", null=True, blank=True)
    status = models.CharField(max_length=20, choices=VaStatus.choices, default=VaStatus.AKTIF, db_index=True)
    slots = models.ManyToManyField(TicketSlot, blank=True, related_name="va_notices")
    customer_claimed_at = models.DateTimeField(null=True, blank=True)
    screenshot = models.FileField(upload_to=private_upload_to, blank=True)
    note = models.TextField("catatan", blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                   on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "info VA"
        verbose_name_plural = "info VA"

    def __str__(self):
        return f"{self.order.code} VA {self.bank}"


class OrderTimeline(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="timeline")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=24, choices=OrderStatus.choices, blank=True)
    title = models.CharField("judul", max_length=150)
    message = models.TextField("pesan", blank=True)
    is_public = models.BooleanField("tampil ke customer", default=True)
    created_by_label = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "riwayat pesanan"
        verbose_name_plural = "riwayat pesanan"

    def __str__(self):
        return f"{self.order.code}: {self.title}"
