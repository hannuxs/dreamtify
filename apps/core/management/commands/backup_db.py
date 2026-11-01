"""Backup database ke backups/dreamtify-YYYYMMDD-HHMM.sql.gz + salin media (docs/09 §9)."""
import logging

from django.core.management.base import BaseCommand, CommandError

from apps.core.backup import BackupError, run_backup

logger = logging.getLogger("dreamtify.daily")


class Command(BaseCommand):
    help = "Backup database (mariadb-dump) dengan rotasi, lalu salin media."

    def add_arguments(self, parser):
        parser.add_argument("--no-media", action="store_true", help="Lewati salin media")

    def handle(self, *args, **options):
        try:
            result = run_backup(include_media=not options["no_media"])
        except BackupError as exc:
            logger.error("backup_db gagal — %s", exc)
            raise CommandError(str(exc)) from exc
        summary = (f"{result['file'].name} ({result['size'] / 1024:.0f} KB), {result['removed']} backup lama dihapus. "
                   f"{result['media']}")
        logger.info("backup_db — %s", summary)
        self.stdout.write(f"[OK] {summary}")
