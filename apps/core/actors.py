"""Siapa yang melakukan aksi — dipakai services untuk AuditLog & timeline."""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Actor:
    label: str
    user: Optional[object] = None  # django User
    ip: Optional[str] = None
    kind: str = "system"  # system | customer | staff

    @classmethod
    def system(cls) -> "Actor":
        return cls(label="sistem", kind="system")

    @classmethod
    def customer(cls, order_code: str, ip: Optional[str] = None) -> "Actor":
        return cls(label=f"customer {order_code}", ip=ip, kind="customer")

    @classmethod
    def staff(cls, user, ip: Optional[str] = None) -> "Actor":
        return cls(label=user.get_username(), user=user, ip=ip, kind="staff")

    @property
    def is_staff(self) -> bool:
        return self.kind == "staff"

    @property
    def is_customer(self) -> bool:
        return self.kind == "customer"

    @property
    def public_label(self) -> str:
        """Label yang aman ditampilkan ke customer di timeline."""
        return {"staff": "Tim Dreamtify", "customer": "Kamu"}.get(self.kind, "Sistem")
