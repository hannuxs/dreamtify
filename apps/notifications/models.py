from django.conf import settings
from django.db import models

from apps.core.enums import NotificationChannel, NotificationStatus
from apps.core.models import TimeStampedModel


class MessageTemplate(TimeStampedModel):
    """Template pesan WA/email (docs/08). Placeholder: {nama}, {kode}, dst."""

    key = models.CharField(max_length=50, unique=True)
    title = models.CharField("judul", max_length=150)
    body = models.TextField("isi")
    is_active = models.BooleanField("aktif", default=True)
    send_email = models.BooleanField("kirim juga lewat email", default=True)
    # True setelah diubah Owner → seed_initial tidak menimpanya
    is_customized = models.BooleanField(default=False, editable=False)

    class Meta:
        ordering = ["key"]
        verbose_name = "template pesan"
        verbose_name_plural = "template pesan"

    def __str__(self):
        return self.key


class Notification(TimeStampedModel):
    order = models.ForeignKey("orders.Order", on_delete=models.CASCADE, related_name="notifications")
    template_key = models.CharField(max_length=50)
    channel = models.CharField(max_length=8, choices=NotificationChannel.choices, default=NotificationChannel.WA)
    recipient = models.CharField("penerima", max_length=254)
    rendered_text = models.TextField("isi pesan")
    status = models.CharField(max_length=16, choices=NotificationStatus.choices,
                              default=NotificationStatus.PERLU_DIKIRIM, db_index=True)
    sent_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                on_delete=models.SET_NULL, related_name="+")
    sent_at = models.DateTimeField(null=True, blank=True)
    dedupe_key = models.CharField(max_length=191, unique=True,
                                  help_text="Mencegah kabar ganda, mis. DRM-ABC123:FEE_DITERIMA:WA")
    error = models.TextField(blank=True)

    class Meta:
        ordering = ["created_at", "id"]
        verbose_name = "kabar"
        verbose_name_plural = "kabar"

    def __str__(self):
        return f"{self.order_id} {self.template_key} {self.channel}"

    @property
    def template_title(self) -> str:
        from .defaults import DEFAULT_TEMPLATES

        tpl = MessageTemplate.objects.filter(key=self.template_key).only("title").first()
        if tpl:
            return tpl.title
        return DEFAULT_TEMPLATES.get(self.template_key, (self.template_key,))[0]
