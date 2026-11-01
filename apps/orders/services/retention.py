"""Retensi data sensitif (docs/09 §3, ASUMSI C12).

Untuk event SELESAI/DIBATALKAN/ARSIP yang `first_show_date` + retensi sudah lewat: kosongkan NIK &
tanggal lahir, rekening refund (bila refund sudah beres), dan hapus file privat yang tak diperlukan.
Bukti transfer & bukti refund disimpan sebagai catatan keuangan. Aman dijalankan berulang.
"""
from dataclasses import asdict, dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.core import audit
from apps.core.actors import Actor
from apps.core.enums import EventStatus
from apps.core.models import SiteSetting
from apps.events.models import Event
from apps.orders.models import Order, OrderLine, TicketSlot, VaNotice
from apps.orders.services import settlement

FINISHED_STATUSES = (EventStatus.SELESAI, EventStatus.DIBATALKAN, EventStatus.ARSIP)


@dataclass
class PurgeCounts:
    lines: int = 0  # baris tiket yang NIK/tanggal lahirnya dikosongkan
    accounts: int = 0  # rekening refund dikosongkan
    accounts_kept: int = 0  # rekening dipertahankan karena refund belum selesai
    files: int = 0  # screenshot VA, foto serah terima, e-tiket

    def add(self, other: "PurgeCounts") -> None:
        for key, value in asdict(other).items():
            setattr(self, key, getattr(self, key) + value)


def due_events(today=None):
    today = today or timezone.localdate()
    cutoff = today - timedelta(days=SiteSetting.load().sensitive_data_retention_days)
    return Event.objects.filter(status__in=FINISHED_STATUSES, first_show_date__lt=cutoff)


def _lines(event):
    return OrderLine.objects.filter(Q(holder_nik_hash__gt="") | Q(holder_birth_date__isnull=False), order__event=event)


def _accounts(event):
    orders = Order.objects.filter(event=event).exclude(refund_account_number="")
    done, kept = [], 0
    for order in orders.prefetch_related("lines__slots", "payments"):
        if settlement.summarize(order).refund_due > 0:
            kept += 1
        else:
            done.append(order.pk)
    return done, kept


def _files(event) -> list:
    """[(objek, nama field)] — e-tiket ikut dihapus karena memuat data pemegang."""
    found = []
    for slot in TicketSlot.objects.filter(line__order__event=event).exclude(handover_photo="", eticket_file=""):
        found += [(slot, name) for name in ("handover_photo", "eticket_file") if getattr(slot, name)]
    found += [(va, "screenshot") for va in VaNotice.objects.filter(order__event=event).exclude(screenshot="")]
    return found


@transaction.atomic
def purge_event(event, *, dry_run: bool = False) -> PurgeCounts:
    lines = _lines(event)
    account_ids, kept = _accounts(event)
    files = _files(event)
    counts = PurgeCounts(lines=lines.count(), accounts=len(account_ids), accounts_kept=kept, files=len(files))
    if dry_run:
        return counts
    # holder_nik_hash ikut dikosongkan: hash tetap data turunan NIK; 4 digit terakhir tersisa untuk tampilan
    lines.update(holder_nik="", holder_nik_hash="", holder_birth_date=None)
    Order.objects.filter(pk__in=account_ids).update(refund_account_number="")
    for obj, name in files:
        getattr(obj, name).delete(save=True)
    if counts.lines or counts.accounts or counts.files:
        audit.log("data.purge", actor=Actor.system(), obj=event, summary=f"Data sensitif dihapus: {event.name}",
                  data=asdict(counts))
    return counts


def purge_due(*, dry_run: bool = False, today=None) -> tuple[list, PurgeCounts]:
    total = PurgeCounts()
    events = list(due_events(today))
    for event in events:
        total.add(purge_event(event, dry_run=dry_run))
    return events, total
