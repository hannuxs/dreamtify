import sys

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = ("Cek koneksi database. Keluaran: OK, OK:TZ (tabel zona waktu MariaDB belum diisi), "
            "atau GAGAL:<kode MariaDB>:<pesan>.")

    def handle(self, *args, **options):
        try:
            connection.ensure_connection()
        except OperationalError as exc:
            code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else 0
            message = exc.args[1] if len(exc.args) > 1 else str(exc)
            self.stdout.write(f"GAGAL:{code}:{message}")
            sys.exit(1)
        if connection.vendor == "mysql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT CONVERT_TZ('2000-01-01 00:00:00', 'UTC', %s)", [settings.TIME_ZONE])
                if cursor.fetchone()[0] is None:
                    self.stdout.write("OK:TZ")
                    return
        self.stdout.write("OK")
