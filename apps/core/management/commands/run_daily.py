"""Tugas harian: hapus data sensitif lalu backup. Log ke logs/daily.log.

Hapus dulu agar backup hari ini sudah bersih. Bila satu langkah gagal, langkah lain tetap dijalankan
dan perintah berakhir dengan kode gagal supaya Scheduled Task menandainya.
"""
import logging

from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger("dreamtify.daily")
STEPS = ("purge_sensitive_data", "backup_db")


class Command(BaseCommand):
    help = "Tugas harian Dreamtify: purge_sensitive_data + backup_db."

    def handle(self, *args, **options):
        failed = []
        for step in STEPS:
            try:
                call_command(step, stdout=self.stdout)
            except Exception as exc:  # langkah berikutnya tetap harus berjalan
                failed.append(step)
                logger.exception("run_daily: %s gagal", step)
                self.stderr.write(f"[GAGAL] {step}: {exc}")
        if failed:
            raise CommandError(f"Tugas harian gagal: {', '.join(failed)}")
        logger.info("run_daily selesai")
        self.stdout.write("[OK] Tugas harian selesai")
