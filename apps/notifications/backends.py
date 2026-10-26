"""
"Pintu" pengiriman kabar (docs/08 §1). Pemanggil hanya memakai antarmuka
`Backend.send(notification)`, sehingga kelak bisa ganti ke WA gateway berbayar
tanpa mengubah kode lain.
"""
import logging
from urllib.parse import quote

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.enums import NotificationStatus

logger = logging.getLogger(__name__)


class Backend:
    def send(self, notification) -> bool:  # pragma: no cover - antarmuka
        raise NotImplementedError


class ManualWhatsAppBackend(Backend):
    """Default: admin mengirim sendiri lewat tombol click-to-chat (gratis)."""

    @staticmethod
    def url(notification) -> str:
        number = "".join(ch for ch in notification.recipient if ch.isdigit())
        return f"https://wa.me/{number}?text={quote(notification.rendered_text)}"

    def send(self, notification) -> bool:
        # Tidak ada pengiriman otomatis: admin membuka url() lalu menekan kirim di WhatsApp.
        return False


class EmailBackend(Backend):
    """Email otomatis (SMTP dari .env). Dipakai bila SiteSetting.email_notifications_enabled."""

    def send(self, notification) -> bool:
        from apps.core.models import SiteSetting

        order = notification.order
        site = SiteSetting.load()
        title = notification.template_title or "Kabar pesanan"
        context = {"brand": site.brand_name, "tagline": site.tagline, "title": title, "order": order,
                   "text": notification.rendered_text, "site_url": settings.SITE_URL}
        message = EmailMultiAlternatives(
            subject=f"[{site.brand_name}] {title} — {order.code}",
            body=render_to_string("emails/notification.txt", context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[notification.recipient],
        )
        message.attach_alternative(render_to_string("emails/notification.html", context), "text/html")
        try:
            message.send()
        except Exception as exc:  # SMTP gagal: dicatat, tidak menggagalkan transaksi bisnis
            logger.warning("Email %s gagal dikirim: %s", notification.pk, exc.__class__.__name__)
            notification.status = NotificationStatus.GAGAL
            notification.error = exc.__class__.__name__
            notification.save(update_fields=["status", "error", "updated_at"])
            return False
        notification.status = NotificationStatus.TERKIRIM
        notification.sent_at = timezone.now()
        notification.save(update_fields=["status", "sent_at", "updated_at"])
        return True


class HttpWhatsAppGatewayBackend(Backend):
    """Stub WA gateway berbayar (Fonnte / Wablas / dsb.) — BELUM AKTIF.

    Cara mengaktifkan kelak:
    1. Tambah ke .env: WA_GATEWAY_URL, WA_GATEWAY_TOKEN.
    2. Implementasikan `send()`: POST {target: notification.recipient, message: notification.rendered_text}
       dengan header Authorization: token. Tandai TERKIRIM bila HTTP 200, GAGAL + error bila tidak.
    3. Di `notifications.services._deliver`, panggil backend ini untuk channel WA
       (sebagai ganti menunggu admin menekan tombol di Kotak Kabar).
    Tidak memakai dependensi baru: cukup `urllib.request`.
    """

    def send(self, notification) -> bool:
        raise NotImplementedError("WA gateway belum diaktifkan. Lihat docstring HttpWhatsAppGatewayBackend.")
