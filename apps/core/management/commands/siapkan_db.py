"""
Menyiapkan database sesuai `.env` (idempoten, aman dijalankan setiap start):
buat database bila belum ada, buat/lengkapi semua tabel, isi data awal.

Berjalan otomatis lewat dev.bat, prod.bat, install.bat. Jadi setelah DB_HOST / DB_PORT / DB_USER /
DB_PASSWORD / DB_NAME diubah, cukup jalankan ulang web. Data lama TIDAK ikut pindah (lihat docs/INSTALASI-SERVER.md).
"""
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import NotSupportedError, connection
from django.db.utils import OperationalError

ACCESS_DENIED = 1045
DB_ACCESS_DENIED = 1044
UNKNOWN_DATABASE = 1049

# Kode error MariaDB → apa yang harus dilakukan pemilik server
HINTS = {
    ACCESS_DENIED: "User/sandi ditolak. Cek DB_USER & DB_PASSWORD di .env, dan pastikan user boleh login dari alamat web ini.",
    DB_ACCESS_DENIED: "User tidak punya hak pada database ini. Jalankan GRANT ALL di server MariaDB (lihat docs/INSTALASI-SERVER.md).",
    1130: "Server MariaDB menolak alamat komputer ini. Buat user untuk IP web ini: 'nama'@'IP-web' (lihat docs/INSTALASI-SERVER.md).",
    2002: "Server MariaDB tidak bisa dihubungi. Cek DB_HOST, DB_PORT, dan layanan MariaDB.",
    2003: "Server MariaDB tidak bisa dihubungi. Cek DB_HOST, DB_PORT, firewall, dan bind-address di server MariaDB.",
    2005: "Alamat DB_HOST tidak dikenal. Cek penulisan DB_HOST di .env.",
    2013: "Koneksi ke MariaDB terputus. Cek firewall dan bind-address di server MariaDB.",
    2026: "Sertifikat server MariaDB tidak terverifikasi. Isi DB_SSL_CA di .env (lihat docs/INSTALASI-SERVER.md).",
}


def error_code(exc) -> int:
    return exc.args[0] if exc.args and isinstance(exc.args[0], int) else 0


def describe(exc) -> str:
    code = error_code(exc)
    detail = exc.args[1] if len(exc.args) > 1 else str(exc)
    return f"{HINTS.get(code, 'Koneksi database gagal.')} [MariaDB {code}: {detail}]"


class Command(BaseCommand):
    help = "Buat database & semua tabel sesuai .env, lalu isi data awal (aman diulang)."

    def handle(self, *args, **options):
        db = settings.DATABASES["default"]
        self.stdout.write(f"Database: {db['NAME']} di {db['HOST']}:{db['PORT']} (user {db['USER']})")
        try:
            self._ensure_database(db["NAME"])
            call_command("migrate", interactive=False, verbosity=0, stdout=self.stdout)
        except NotSupportedError as exc:
            raise CommandError(f"Versi MariaDB tidak didukung (minimal 10.5): {exc}") from exc
        except OperationalError as exc:
            raise CommandError(describe(exc)) from exc
        self.stdout.write(self.style.SUCCESS("[OK] Semua tabel lengkap"))
        call_command("createcachetable", verbosity=0, stdout=self.stdout)
        call_command("seed_initial", verbosity=0, stdout=self.stdout)
        self.stdout.write(self.style.SUCCESS("[OK] Data awal terisi"))
        self._warn_charset()
        if not get_user_model().objects.filter(is_active=True, is_superuser=True).exists() and \
                not get_user_model().objects.filter(is_active=True, groups__name="Owner").exists():
            self.stdout.write(self.style.WARNING("[PERHATIAN] Belum ada akun Owner. Jalankan: manage.py buat_owner"))

    def _ensure_database(self, name: str) -> None:
        try:
            connection.ensure_connection()
            return
        except OperationalError as exc:
            if error_code(exc) != UNKNOWN_DATABASE:
                raise
        try:
            with connection._nodb_cursor() as cursor:
                cursor.execute(f"CREATE DATABASE IF NOT EXISTS {connection.ops.quote_name(name)} "
                               "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        except OperationalError as exc:
            if error_code(exc) in (ACCESS_DENIED, DB_ACCESS_DENIED):
                raise CommandError(f"Database '{name}' belum ada dan user tidak boleh membuatnya. "
                                   f"Buat dulu di server MariaDB (lihat docs/INSTALASI-SERVER.md).") from exc
            raise
        connection.close()
        connection.ensure_connection()
        self.stdout.write(self.style.SUCCESS(f"[OK] Database '{name}' dibuat"))

    def _warn_charset(self) -> None:
        with connection.cursor() as cursor:
            cursor.execute("SELECT @@character_set_database")
            charset = cursor.fetchone()[0]
        if charset != "utf8mb4":
            self.stdout.write(self.style.WARNING(f"[PERHATIAN] Charset database '{charset}', seharusnya utf8mb4 (emoji & nama bisa rusak)."))
