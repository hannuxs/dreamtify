"""Fase 12: header & CSP, izin semua URL dashboard, log, retensi, backup, tugas harian (docs/09, docs/11 §1)."""
import gzip
import logging
import os
import re
import stat
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest
from django.conf import settings as dj_settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.base import ContentFile
from django.core.management import CommandError, call_command
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core import backup
from apps.core.enums import EventStatus, SlotResult
from apps.core.log_filters import MaskingFormatter, MaskSensitiveFilter
from apps.core.models import AuditLog, SiteSetting
from apps.dashboard import urls as dashboard_urls
from apps.events.models import Event
from apps.orders.models import OrderLine, VaNotice
from apps.orders.services import retention, transitions, updates

from .factories import CUSTOMER, JASWAR, VA_BCA, line, make_fanmeet, make_order, pay, slots

pytestmark = pytest.mark.django_db
User = get_user_model()
ROOT = Path(dj_settings.BASE_DIR)
NIK = "3171012345678901"


@pytest.fixture(autouse=True)
def setup(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path / "media"
    call_command("seed_initial", verbosity=0)


# --- Header ---------------------------------------------------------------------------

def test_csp_ketat_di_semua_jenis_halaman(client):
    for url in ("/", "/faq/", "/kelola/login/", "/halaman-tidak-ada/"):
        response = client.get(url)
        csp = response["Content-Security-Policy"]
        assert "default-src 'self'" in csp and "script-src 'self'" in csp and "frame-ancestors 'none'" in csp
        assert "unsafe-inline" not in csp and "unsafe-eval" not in csp
        assert response["X-Content-Type-Options"] == "nosniff" and response["X-Frame-Options"] == "DENY"
        assert response["Referrer-Policy"] == "same-origin" and "camera=()" in response["Permissions-Policy"]


def test_template_tanpa_skrip_dan_gaya_inline():
    pattern = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>|<style\b|\sstyle=\"|\son[a-z]+=\"", re.I)
    offenders = []
    for path in (ROOT / "templates").rglob("*.html"):
        if "emails" in path.parts:  # email tidak dimuat browser dengan CSP web ini
            continue
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(path.name)
    assert not offenders


def test_check_deploy_tanpa_error():
    env = {**os.environ, "DJANGO_ENV": "prod", "DJANGO_SETTINGS_MODULE": "config.settings.prod",
           "SECRET_KEY": "kunci-uji-deploy-yang-cukup-panjang-" + "x" * 40}
    result = subprocess.run([sys.executable, "manage.py", "check", "--deploy", "--fail-level", "ERROR"], cwd=ROOT, env=env,
                            capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr[-800:]


# --- Izin -----------------------------------------------------------------------------

def _dashboard_paths():
    args = {"int": 1, "str": "DRM-AAAAAA", "slug": "contoh"}
    for pattern in dashboard_urls.urlpatterns:
        if pattern.name in ("login", "logout"):
            continue
        kwargs = {name: args[type(conv).__name__.replace("Converter", "").lower().replace("string", "str")]
                  for name, conv in pattern.pattern.converters.items()}
        yield reverse(f"dashboard:{pattern.name}", kwargs=kwargs)


def test_semua_url_kelola_menolak_anonim_dan_non_staf(client):
    paths = list(_dashboard_paths())
    assert len(paths) > 50
    plain = User.objects.create_user("pelanggan", password="rahasia-panjang-1")
    logged_in = Client()
    logged_in.force_login(plain)
    for path in paths:
        response = client.get(path)
        assert response.status_code == 302 and "/kelola/login/" in response["Location"], path
        assert logged_in.get(path).status_code in (302, 403), path


def test_url_owner_menolak_admin():
    user = User.objects.create_user("admin-izin", password="rahasia-panjang-1", is_staff=True)
    user.groups.add(Group.objects.get(name="Admin"))
    staff = Client()
    staff.force_login(user)
    for path in ("/kelola/pengaturan/brand/", "/kelola/pengguna/", "/kelola/log/", "/kelola/pengaturan/template/FEE_DITERIMA/",
                 "/kelola/rekap/keuangan.xlsx?event=1"):
        assert staff.get(path).status_code == 403, path
    assert staff.get("/kelola/sistem/").status_code == 302  # Django admin hanya superuser



# --- Log ------------------------------------------------------------------------------

def test_file_log_tidak_memuat_nik_atau_rekening(tmp_path):
    path = tmp_path / "app.log"
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.addFilter(MaskSensitiveFilter())
    handler.setFormatter(MaskingFormatter("{levelname} {message}", style="{"))
    logger = logging.getLogger("uji.keamanan")
    logger.addHandler(handler)
    logger.propagate = False
    logger.setLevel(logging.INFO)
    try:
        logger.info("Pesanan NIK %s rekening %s", NIK, "1234567890123")
        logger.info("Format spasi 3171 0123 4567 8901")
        try:
            raise ValueError(f"gagal memproses {NIK}")
        except ValueError:
            logger.exception("Galat tiket")
    finally:
        logger.removeHandler(handler)
        handler.close()
    text = path.read_text(encoding="utf-8")
    assert NIK not in text and "1234567890123" not in text and "3171 0123" not in text
    assert "8901" in text and "ValueError" in text


# --- Retensi --------------------------------------------------------------------------

def event_done(admin, *, days_ago=31, status=EventStatus.SELESAI, method=VA_BCA):
    fx = make_fanmeet()
    order = make_order(fx, [line(fx, JASWAR, 2, ("CAT 3", "CAT 2", "CAT 1"))], method=method)
    pay(order, 400_000, admin)
    transitions.start_war(fx.phase, actor=admin)
    s1, s2 = slots(order)
    transitions.set_slot_result(s1, SlotResult.SECURED, actor=admin, category=fx.cat("CAT 3"))
    transitions.set_slot_result(s2, SlotResult.GAGAL, actor=admin)
    Event.objects.filter(pk=fx.event.pk).update(status=status, first_show_date=timezone.localdate() - timedelta(days=days_ago))
    return fx, order


def test_purge_menghapus_data_sensitif_dan_menyimpan_bukti(admin):
    fx, order = event_done(admin)
    slot = slots(order)[0]
    slot.handover_photo.save("foto.jpg", ContentFile(b"f"))
    slot.eticket_file.save("tiket.pdf", ContentFile(b"e"))
    va = VaNotice.objects.create(order=order, bank="BCA", va_number="123456789", amount=1, source="ADMIN")
    va.screenshot.save("va.jpg", ContentFile(b"v"))
    payment = order.payments.first()
    payment.proof.save("bukti.jpg", ContentFile(b"b"))
    updates.set_refund_account(order, bank="BCA", number="1234567890", holder="Rina", actor=CUSTOMER)
    photo_path = Path(slot.handover_photo.path)

    call_command("purge_sensitive_data", "--dry-run", verbosity=0)
    ln = OrderLine.objects.get(order=order)
    assert ln.holder_nik == NIK and photo_path.exists() and not AuditLog.objects.filter(action="data.purge").exists()

    # Refund belum ditransfer → rekening tetap ada
    call_command("purge_sensitive_data", verbosity=0)
    ln.refresh_from_db()
    order.refresh_from_db()
    assert ln.holder_nik == "" and ln.holder_birth_date is None and ln.holder_nik_hash == "" and ln.holder_nik_last4 == "8901"
    assert order.refund_account_number == "1234567890"
    assert not photo_path.exists()
    slot.refresh_from_db()
    va.refresh_from_db()
    assert not slot.handover_photo and not slot.eticket_file and not va.screenshot
    payment.refresh_from_db()
    assert payment.proof and Path(payment.proof.path).exists()
    log = AuditLog.objects.get(action="data.purge")
    assert log.data["lines"] == 1 and log.data["files"] == 3 and log.data["accounts_kept"] == 1 and NIK not in str(log.data)

    # Setelah refund selesai rekening ikut terhapus; jalankan ulang aman
    transitions.record_refund(order, amount=150_000, actor=admin, transfer_date=date(2026, 11, 1))
    call_command("purge_sensitive_data", verbosity=0)
    order.refresh_from_db()
    assert order.refund_account_number == ""
    call_command("purge_sensitive_data", verbosity=0)
    assert AuditLog.objects.filter(action="data.purge").count() == 2


def test_purge_mematuhi_retensi_dan_status(admin):
    recent, recent_order = event_done(admin, days_ago=29)
    open_event, open_order = event_done(admin, status=EventStatus.TAMPIL)
    archived, archived_order = event_done(admin, status=EventStatus.ARSIP)
    call_command("purge_sensitive_data", verbosity=0)
    assert OrderLine.objects.get(order=recent_order).holder_nik == NIK
    assert OrderLine.objects.get(order=open_order).holder_nik == NIK
    assert OrderLine.objects.get(order=archived_order).holder_nik == ""
    site = SiteSetting.load()
    site.sensitive_data_retention_days = 7
    site.save()
    call_command("purge_sensitive_data", verbosity=0)
    assert OrderLine.objects.get(order=recent_order).holder_nik == ""


def test_lihat_nik_setelah_purge_tidak_error(client, admin):
    fx, order = event_done(admin)
    call_command("purge_sensitive_data", verbosity=0)
    owner = User.objects.create_user("owner-purge", password="rahasia-panjang-1", is_staff=True)
    owner.groups.add(Group.objects.get(name="Owner"))
    client.force_login(owner)
    line_id = OrderLine.objects.get(order=order).pk
    response = client.post(f"/kelola/pesanan/{order.code}/nik/{line_id}/")
    assert response.status_code == 200 and NIK not in response.content.decode()


# --- Backup ---------------------------------------------------------------------------

@pytest.fixture
def fake_dump(settings, tmp_path, monkeypatch):
    """mariadb-dump palsu: mencatat argumen & isi file opsi, menulis SQL ke stdout."""
    record = tmp_path / "argv.txt"
    script = tmp_path / "dump.py"
    script.write_text(
        "import sys\n"
        f"open(r'{record}', 'w').write(' '.join(sys.argv[1:]) + '\\n' + open(sys.argv[1].split('=', 1)[1]).read())\n"
        "sys.stdout.write('CREATE TABLE contoh (id INT);\\n')\n"
        "sys.exit(int(__import__('os').environ.get('DUMP_EXIT', '0')))\n")
    wrapper = tmp_path / ("dump.bat" if sys.platform == "win32" else "dump.sh")
    if sys.platform == "win32":
        wrapper.write_text(f'@"{sys.executable}" "{script}" %*\n@exit /b %ERRORLEVEL%\n')
    else:
        wrapper.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{script}" "$@"\n')
        wrapper.chmod(wrapper.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setattr(backup, "find_dump", lambda: str(wrapper))
    settings.BACKUP_DIR = tmp_path / "backups"
    settings.BACKUP_KEEP = 3
    return record


def test_backup_menulis_gzip_dan_sandi_tidak_di_argumen(fake_dump, settings, monkeypatch):
    monkeypatch.setitem(settings.DATABASES["default"], "PASSWORD", 'sandi"rahasia\\x')
    call_command("backup_db", "--no-media", verbosity=0)
    files = list(Path(settings.BACKUP_DIR).glob("dreamtify-*.sql.gz"))
    assert len(files) == 1 and re.fullmatch(r"dreamtify-\d{8}-\d{4}\.sql\.gz", files[0].name)
    with gzip.open(files[0], "rt") as stream:
        assert "CREATE TABLE contoh" in stream.read()
    argv, _, options = fake_dump.read_text().partition("\n")
    assert "--single-transaction" in argv and "--routines" in argv and "rahasia" not in argv
    assert 'password="sandi\\"rahasia\\\\x"' in options
    assert not Path(argv.split()[0].split("=", 1)[1]).exists()  # file opsi sementara terhapus


def test_backup_gagal_tidak_meninggalkan_file(fake_dump, settings, monkeypatch):
    monkeypatch.setenv("DUMP_EXIT", "2")
    with pytest.raises(CommandError):
        call_command("backup_db", "--no-media", verbosity=0)
    assert not list(Path(settings.BACKUP_DIR).iterdir())


def test_rotasi_menyimpan_yang_terbaru(tmp_path):
    for day in range(1, 6):
        (tmp_path / f"dreamtify-2026110{day}-0300.sql.gz").write_bytes(b"x")
    (tmp_path / "catatan.txt").write_text("jangan dihapus")
    removed = backup.rotate(tmp_path, 3)
    assert [p.name for p in removed] == ["dreamtify-20261102-0300.sql.gz", "dreamtify-20261101-0300.sql.gz"]
    assert (tmp_path / "catatan.txt").exists()


def test_dump_tidak_ditemukan_pesan_jelas(settings, monkeypatch):
    settings.MARIADB_BIN = ""
    monkeypatch.setattr(backup, "WINDOWS_BINS", ())
    monkeypatch.setattr(backup.shutil, "which", lambda name: None)
    with pytest.raises(backup.BackupError, match="MARIADB_BIN"):
        backup.find_dump()


def test_run_daily_tetap_lanjut_bila_purge_gagal(monkeypatch):
    calls = []

    def fake(step, **kwargs):
        calls.append(step)
        if step == "purge_sensitive_data":
            raise RuntimeError("purge rusak")

    monkeypatch.setattr("apps.core.management.commands.run_daily.call_command", fake)
    with pytest.raises(CommandError, match="purge_sensitive_data"):
        call_command("run_daily", verbosity=0)
    assert calls == ["purge_sensitive_data", "backup_db"]


def test_due_events_tanpa_tanggal_dilewati(admin):
    fx, _ = event_done(admin)
    Event.objects.filter(pk=fx.event.pk).update(first_show_date=None)
    assert not retention.due_events().exists()
