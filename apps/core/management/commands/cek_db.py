import sys

from django.core.management.base import BaseCommand
from django.db import connection
from django.db.utils import OperationalError


class Command(BaseCommand):
    help = "Cek koneksi database. Keluaran: OK, atau GAGAL:<kode MariaDB>:<pesan>."

    def handle(self, *args, **options):
        try:
            connection.ensure_connection()
        except OperationalError as exc:
            code = exc.args[0] if exc.args and isinstance(exc.args[0], int) else 0
            message = exc.args[1] if len(exc.args) > 1 else str(exc)
            self.stdout.write(f"GAGAL:{code}:{message}")
            sys.exit(1)
        self.stdout.write("OK")
