"""Alur testimoni: kirim customer, tambah manual, moderasi (docs/05 §11, ASUMSI C15).

Gambar disimpan privat (`image`) sampai disetujui; baru disalin ke media/public/ (`public_image`)
dan dihapus lagi dari sana bila disembunyikan, supaya URL publiknya mati.
"""
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Avg, Count
from django.utils import timezone

from apps.core import audit
from apps.core.enums import OrderStatus, TestimonialSource, TestimonialStatus
from apps.core.uploads import process_public_image
from apps.orders.models import Order
from apps.orders.services.transitions import InvalidTransition

from .models import Testimonial


def can_submit(order) -> bool:
    return order.status == OrderStatus.SELESAI and not order.testimonials.exists()


@transaction.atomic
def submit_from_customer(order, *, display_name: str, rating: int, text: str, image=None, actor) -> Testimonial:
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status != OrderStatus.SELESAI:
        raise InvalidTransition("Testimoni bisa dikirim setelah pesanan selesai.")
    if order.testimonials.exists():
        raise InvalidTransition("Testimoni untuk pesanan ini sudah terkirim.")
    testimonial = Testimonial(display_name=display_name, event=order.event, order=order, rating=rating, text=text,
                              source=TestimonialSource.CUSTOMER, status=TestimonialStatus.MENUNGGU,
                              consent_publish=True)
    if image:
        testimonial.image.save(f"testimoni-{order.code}.jpg", process_public_image(image, name="testimoni"), save=False)
    testimonial.save()
    audit.log("testimonial.submit", actor=actor, obj=testimonial, summary=f"Testimoni baru dari {order.code}")
    return testimonial


def create_manual(*, display_name: str, rating: int, text: str, event=None, image=None, actor) -> Testimonial:
    """ASUMSI: testimoni yang ditambahkan admin (screenshot chat) langsung tampil."""
    testimonial = Testimonial(display_name=display_name, event=event, rating=rating, text=text,
                              source=TestimonialSource.ADMIN, consent_publish=True)
    if image:
        testimonial.image.save("testimoni-admin.jpg", process_public_image(image, name="testimoni"), save=False)
    testimonial.save()
    return approve(testimonial, actor=actor)


def _publish_image(testimonial) -> None:
    if testimonial.image and not testimonial.public_image:
        with testimonial.image.open("rb") as handle:
            testimonial.public_image.save("testimoni.jpg", ContentFile(handle.read()), save=False)


def _unpublish_image(testimonial) -> None:
    if testimonial.public_image:
        testimonial.public_image.delete(save=False)


def approve(testimonial, *, actor) -> Testimonial:
    _publish_image(testimonial)
    testimonial.status = TestimonialStatus.TAMPIL
    testimonial.approved_by = actor.user
    testimonial.approved_at = timezone.now()
    testimonial.save()
    audit.log("testimonial.approve", actor=actor, obj=testimonial, summary=f"Testimoni disetujui: {testimonial.display_name}")
    return testimonial


def hide(testimonial, *, actor) -> Testimonial:
    _unpublish_image(testimonial)
    testimonial.status = TestimonialStatus.DISEMBUNYIKAN
    testimonial.is_featured = False
    testimonial.save()
    audit.log("testimonial.hide", actor=actor, obj=testimonial, summary=f"Testimoni disembunyikan: {testimonial.display_name}")
    return testimonial


def toggle_featured(testimonial, *, actor) -> Testimonial:
    if testimonial.status != TestimonialStatus.TAMPIL:
        raise InvalidTransition("Hanya testimoni yang tampil bisa dijadikan unggulan.")
    testimonial.is_featured = not testimonial.is_featured
    testimonial.save(update_fields=["is_featured", "updated_at"])
    audit.log("testimonial.feature", actor=actor, obj=testimonial, summary=f"Unggulan: {testimonial.is_featured}")
    return testimonial


def update_text(testimonial, *, display_name: str, text: str, actor) -> Testimonial:
    testimonial.display_name, testimonial.text = display_name, text
    testimonial.save(update_fields=["display_name", "text", "updated_at"])
    audit.log("testimonial.edit", actor=actor, obj=testimonial, summary="Teks testimoni diubah")
    return testimonial


def delete(testimonial, *, actor) -> None:
    audit.log("testimonial.delete", actor=actor, obj=testimonial, summary=f"Testimoni dihapus: {testimonial.display_name}")
    _unpublish_image(testimonial)
    if testimonial.image:
        testimonial.image.delete(save=False)
    testimonial.delete()


def published(event=None):
    qs = Testimonial.objects.filter(status=TestimonialStatus.TAMPIL, consent_publish=True).select_related("event", "order")
    return qs.filter(event=event) if event else qs


def featured(limit: int = 6) -> list:
    return list(published().filter(is_featured=True)[:limit])


def rating_summary(qs) -> dict:
    return qs.aggregate(total=Count("id"), average=Avg("rating"))
