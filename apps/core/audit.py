"""Menulis AuditLog. Ringkasan & data TIDAK boleh berisi NIK / nomor rekening."""
from .actors import Actor
from .log_filters import mask_sensitive
from .models import AuditLog


def log(action: str, *, actor: Actor, obj=None, summary: str = "", data: dict | None = None) -> AuditLog:
    return AuditLog.objects.create(
        actor=actor.user if actor.is_staff else None,
        actor_label=actor.label[:100],
        action=action,
        object_type=obj._meta.label_lower if obj is not None else "",
        object_id=str(obj.pk) if obj is not None else "",
        # Lapis pengaman: deret angka panjang tetap disamarkan bila terselip
        summary=mask_sensitive(summary),
        data=data or {},
        ip_address=actor.ip,
    )
