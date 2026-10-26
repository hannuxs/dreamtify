from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.enums import TestimonialSource, TestimonialStatus
from apps.core.models import TimeStampedModel
from apps.core.uploads import private_upload_to


class Testimonial(TimeStampedModel):
    display_name = models.CharField("nama tampilan", max_length=80)
    event = models.ForeignKey("events.Event", null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="testimonials")
    order = models.ForeignKey("orders.Order", null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="testimonials",
                              help_text="Terisi → badge 'Pembeli terverifikasi'")
    rating = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(5)])
    text = models.TextField("isi")
    # Disimpan privat dulu; disalin ke media/public/ saat disetujui (fase 11)
    image = models.ImageField("gambar", upload_to=private_upload_to, blank=True)
    source = models.CharField(max_length=10, choices=TestimonialSource.choices,
                              default=TestimonialSource.CUSTOMER)
    status = models.CharField(max_length=14, choices=TestimonialStatus.choices,
                              default=TestimonialStatus.MENUNGGU, db_index=True)
    is_featured = models.BooleanField("unggulan", default=False)
    consent_publish = models.BooleanField("izin dipublikasikan", default=False)
    approved_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name="+")
    approved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "testimoni"
        verbose_name_plural = "testimoni"

    def __str__(self):
        return f"{self.display_name} ({self.rating}★)"
