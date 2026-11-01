"""Hapus data sensitif event yang masa retensinya lewat (docs/09 §3). `--dry-run` hanya menghitung."""
import logging

from django.core.management.base import BaseCommand

from apps.orders.services import retention

logger = logging.getLogger("dreamtify.daily")


class Command(BaseCommand):
    help = "Hapus NIK, tanggal lahir, rekening refund, dan file privat setelah masa retensi."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Tampilkan jumlah tanpa menghapus apa pun")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        events, total = retention.purge_due(dry_run=dry_run)
        prefix = "[SIMULASI] Akan dihapus" if dry_run else "[OK] Dihapus"
        summary = (f"{prefix}: {len(events)} event, {total.lines} baris tiket, {total.accounts} rekening refund "
                   f"({total.accounts_kept} dipertahankan, refund belum selesai), {total.files} file")
        for event in events:
            self.stdout.write(f"     - {event.name}")
        self.stdout.write(summary)
        if not dry_run:
            logger.info("purge_sensitive_data — %s", summary)
