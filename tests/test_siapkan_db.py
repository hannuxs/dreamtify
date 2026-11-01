"""Fase 13: penyiapan database otomatis sesuai .env, akun Owner, skrip Windows."""
import re
from pathlib import Path

import pytest
from django.conf import settings as dj_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from django.db import connection
from django.db.utils import OperationalError

from apps.core import backup
from apps.core.management.commands import siapkan_db

pytestmark = pytest.mark.django_db
ROOT = Path(dj_settings.BASE_DIR)


def test_siapkan_db_idempoten_dan_mengisi_data_awal(capsys):
    call_command("siapkan_db")
    call_command("siapkan_db")
    out = capsys.readouterr().out
    assert "[OK] Semua tabel lengkap" in out and "Belum ada akun Owner" in out
    assert Group.objects.filter(name="Owner").exists()


@pytest.mark.parametrize("code,hint", [
    (1045, "DB_USER"), (1130, "IP-web"), (2003, "bind-address"), (2005, "DB_HOST"), (2026, "DB_SSL_CA"),
])
def test_error_koneksi_dijelaskan(monkeypatch, code, hint):
    def fail():
        raise OperationalError(code, "ditolak")

    monkeypatch.setattr(connection, "ensure_connection", fail)
    with pytest.raises(CommandError, match=hint):
        call_command("siapkan_db")


def test_database_belum_ada_dibuat_otomatis(monkeypatch):
    calls = []
    real = connection.ensure_connection

    def first_unknown():
        calls.append("connect")
        if len(calls) == 1:
            raise OperationalError(1049, "Unknown database")
        return real()

    class Cursor:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql):
            calls.append(sql)

    monkeypatch.setattr(connection, "ensure_connection", first_unknown)
    monkeypatch.setattr(connection, "_nodb_cursor", Cursor)
    monkeypatch.setattr(connection, "close", lambda: None)
    siapkan_db.Command()._ensure_database("db_baru")
    assert any("CREATE DATABASE IF NOT EXISTS `db_baru`" in c and "utf8mb4_unicode_ci" in c for c in calls)


def test_user_tanpa_hak_membuat_database_diberi_arahan(monkeypatch):
    def unknown():
        raise OperationalError(1049, "Unknown database")

    class Denied:
        def __enter__(self):
            raise OperationalError(1044, "Access denied")

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(connection, "ensure_connection", unknown)
    monkeypatch.setattr(connection, "_nodb_cursor", Denied)
    with pytest.raises(CommandError, match="belum ada dan user tidak boleh"):
        siapkan_db.Command()._ensure_database("db_baru")


def test_buat_owner_sekali_dan_memvalidasi_sandi(monkeypatch):
    call_command("seed_initial", verbosity=0)
    monkeypatch.setenv("DREAMTIFY_OWNER_PASSWORD", "pendek")
    with pytest.raises(CommandError):
        call_command("buat_owner", username="pemilik")
    monkeypatch.setenv("DREAMTIFY_OWNER_PASSWORD", "Sandi-Owner-Kuat-2026")
    call_command("buat_owner", username="pemilik")
    user = get_user_model().objects.get(username="pemilik")
    assert user.is_superuser and user.groups.filter(name="Owner").exists()
    call_command("buat_owner", username="pemilik-kedua")
    assert not get_user_model().objects.filter(username="pemilik-kedua").exists()


def test_backup_memakai_sertifikat_ca_dan_tetap_memverifikasi(settings):
    settings.DB_SSL_CA = r"C:\sertifikat\ca.pem"
    path = Path(backup._option_file(settings.DATABASES["default"]))
    try:
        text = path.read_text(encoding="utf-8")
    finally:
        path.unlink()
    assert "ssl-ca=" in text and "ca.pem" in text
    assert "skip-ssl" not in text and "verify-server-cert" not in text


def test_skrip_powershell_ascii_saja():
    # PowerShell 5.1 membaca file tanpa BOM sebagai ANSI
    for path in (ROOT / "scripts").glob("*.ps1"):
        assert path.read_bytes().isascii(), path.name


def test_kontrak_perintah_ada():
    for name in ("install.bat", "dev.bat", "prod.bat", "scripts/layanan.ps1", "scripts/restore.ps1", "scripts/tugas.bat"):
        assert (ROOT / name).is_file(), name


def test_tugas_terjadwal_memakai_mode_produksi():
    common = (ROOT / "scripts/common.ps1").read_text(encoding="utf-8")
    assert re.search(r"tugas\.bat", common) and "'run_periodic'" in common and "'run_daily'" in common
    assert 'set "DJANGO_ENV=prod"' in (ROOT / "scripts/tugas.bat").read_text(encoding="utf-8")


def test_aplikasi_tidak_butuh_tabel_zona_waktu_mariadb():
    """Database di server lain sering tanpa akses root untuk mengisi mysql.time_zone*."""
    pattern = re.compile(r"__(date|year|month|day|hour)\b|date_hierarchy|Trunc[A-Z(]")
    offenders = []
    for path in (ROOT / "apps").rglob("*.py"):
        code = "\n".join(ln.split("#")[0] for ln in path.read_text(encoding="utf-8").splitlines())
        if "migrations" not in path.parts and pattern.search(code):
            offenders.append(path.name)
    assert not offenders
