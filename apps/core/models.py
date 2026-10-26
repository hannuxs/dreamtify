from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from .phone import validate_wa
from .uploads import public_upload_to


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("dibuat", auto_now_add=True)
    updated_at = models.DateTimeField("diubah", auto_now=True)

    class Meta:
        abstract = True


class SiteSetting(TimeStampedModel):
    """Pengaturan situs (singleton, id=1). Ambil lewat `SiteSetting.load()`."""

    brand_name = models.CharField("nama brand", max_length=80, default="Dreamtify")
    tagline = models.CharField(max_length=150, default="Your Dream is Our Priority")
    logo = models.ImageField(upload_to=public_upload_to, blank=True,
                             help_text="Kosong = logo bawaan static/img/logo-dreamtify.png")
    admin_whatsapp = models.CharField("WhatsApp admin", max_length=20, blank=True,
                                      validators=[validate_wa], help_text="Format 62…")
    instagram = models.CharField(max_length=64, blank=True, help_text="Tanpa @")
    contact_email = models.EmailField("email kontak", blank=True)
    general_terms = models.TextField("syarat & ketentuan umum", blank=True)
    privacy_policy = models.TextField("kebijakan privasi", blank=True)
    refund_policy_summary = models.TextField("ringkasan kebijakan refund", blank=True)
    default_fee_payment_window_hours = models.PositiveSmallIntegerField(
        "jendela bayar fee default (jam)", default=24, validators=[MinValueValidator(1)])
    default_booking_slot_fee = models.PositiveBigIntegerField("booking slot default (Rp/tiket)", default=50000)
    sensitive_data_retention_days = models.PositiveSmallIntegerField(
        "retensi data sensitif (hari)", default=30)
    email_notifications_enabled = models.BooleanField("kirim email otomatis", default=False)

    class Meta:
        verbose_name = "pengaturan situs"
        verbose_name_plural = "pengaturan situs"

    def __str__(self):
        return "Pengaturan situs"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls) -> "SiteSetting":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class BankAccount(TimeStampedModel):
    """Rekening tujuan transfer Dreamtify."""

    bank_name = models.CharField("bank", max_length=50)
    account_number = models.CharField("nomor rekening", max_length=40)
    account_holder = models.CharField("atas nama", max_length=120)
    is_active = models.BooleanField("aktif", default=True)
    sort_order = models.PositiveSmallIntegerField("urutan", default=0)
    note = models.CharField("catatan", max_length=200, blank=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "rekening"
        verbose_name_plural = "rekening"
        constraints = [
            models.UniqueConstraint(fields=["bank_name", "account_number"], name="uniq_bank_account"),
        ]

    def __str__(self):
        return f"{self.bank_name} {self.account_number} a.n. {self.account_holder}"


class FaqItem(TimeStampedModel):
    question = models.CharField("pertanyaan", max_length=255)
    answer = models.TextField("jawaban")
    sort_order = models.PositiveSmallIntegerField("urutan", default=0)
    is_active = models.BooleanField("aktif", default=True)

    class Meta:
        ordering = ["sort_order", "id"]
        verbose_name = "FAQ"
        verbose_name_plural = "FAQ"

    def __str__(self):
        return self.question


class AuditLog(models.Model):
    """Jejak audit. TIDAK boleh berisi NIK / nomor rekening (docs/09 §2)."""

    created_at = models.DateTimeField("waktu", auto_now_add=True, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                              on_delete=models.SET_NULL, related_name="+", verbose_name="pengguna")
    actor_label = models.CharField("pelaku", max_length=100)
    action = models.CharField("aksi", max_length=64, db_index=True)
    object_type = models.CharField("jenis objek", max_length=64, blank=True)
    object_id = models.CharField("id objek", max_length=64, blank=True)
    summary = models.TextField("ringkasan", blank=True)
    data = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField("IP", null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "log aktivitas"
        verbose_name_plural = "log aktivitas"
        indexes = [models.Index(fields=["object_type", "object_id"], name="audit_object_idx")]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor_label} {self.action}"
