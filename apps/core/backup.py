"""Backup database & media (docs/09 §9, docs/10 §7).

Kata sandi DB lewat file opsi sementara, tidak pernah lewat argumen baris perintah.
"""
import gzip
import os
import platform
import shutil
import subprocess
import tempfile
from glob import glob
from pathlib import Path

from django.conf import settings
from django.utils import timezone

DUMP_NAMES = ("mariadb-dump.exe", "mysqldump.exe", "mariadb-dump", "mysqldump")
WINDOWS_BINS = (r"C:\Program Files\MariaDB *\bin",)
FILE_PREFIX = "dreamtify-"
# robocopy: kode 0–7 berarti berhasil, ≥8 berarti gagal
ROBOCOPY_FAILED_FROM = 8


class BackupError(Exception):
    pass


def find_dump() -> str:
    folders = [settings.MARIADB_BIN] if settings.MARIADB_BIN else []
    for pattern in WINDOWS_BINS:
        folders += sorted(glob(pattern), reverse=True)
    for folder in folders:
        for name in DUMP_NAMES:
            candidate = Path(folder) / name
            if candidate.is_file():
                return str(candidate)
    for name in DUMP_NAMES:
        found = shutil.which(name)
        if found:
            return found
    raise BackupError("mariadb-dump tidak ditemukan. Isi MARIADB_BIN di .env (folder bin MariaDB).")


def _option_file(db) -> str:
    password = db["PASSWORD"].replace("\\", "\\\\").replace('"', '\\"')
    text = f'[client]\nuser={db["USER"]}\npassword="{password}"\nhost={db["HOST"]}\nport={db["PORT"]}\n'
    handle, path = tempfile.mkstemp(prefix="dreamtify-opt-", suffix=".cnf")
    with os.fdopen(handle, "w", encoding="utf-8") as stream:
        stream.write(text)
    return path


def dump_database(target: Path) -> None:
    """Tulis `.sql.gz`; memakai file sementara agar backup gagal tidak meninggalkan file rusak."""
    db = settings.DATABASES["default"]
    partial = target.with_name(target.name + ".part")
    option_file = _option_file(db)
    command = [find_dump(), f"--defaults-extra-file={option_file}", "--single-transaction", "--routines",
               "--default-character-set=utf8mb4", db["NAME"]]
    try:
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors)
            with gzip.open(partial, "wb") as output:
                shutil.copyfileobj(process.stdout, output)
            process.stdout.close()
            code = process.wait()
            errors.seek(0)
            message = errors.read().decode("utf-8", "replace").strip()
        if code != 0:
            raise BackupError(f"mariadb-dump gagal (kode {code}): {message[:300]}")
        partial.replace(target)
    finally:
        partial.unlink(missing_ok=True)
        Path(option_file).unlink(missing_ok=True)


def rotate(folder: Path, keep: int) -> list:
    files = sorted(folder.glob(f"{FILE_PREFIX}*.sql.gz"), key=lambda p: p.name, reverse=True)
    removed = files[keep:]
    for path in removed:
        path.unlink()
    return removed


def copy_media(folder: Path) -> str:
    source = Path(settings.MEDIA_ROOT)
    if platform.system() != "Windows":
        return "Salin media dilewati (robocopy hanya di Windows)."
    if not source.is_dir():
        return "Folder media belum ada, dilewati."
    code = subprocess.run(["robocopy", str(source), str(folder / "media"), "/MIR", "/XJ", "/R:1", "/W:1",
                           "/NFL", "/NDL", "/NJH", "/NJS", "/NP"], capture_output=True, check=False).returncode
    if code >= ROBOCOPY_FAILED_FROM:
        raise BackupError(f"robocopy media gagal (kode {code}).")
    return "Media tersalin ke backups/media."


def run_backup(*, include_media: bool = True) -> dict:
    folder = Path(settings.BACKUP_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    stamp = timezone.localtime().strftime("%Y%m%d-%H%M")
    target = folder / f"{FILE_PREFIX}{stamp}.sql.gz"
    dump_database(target)
    removed = rotate(folder, settings.BACKUP_KEEP)
    return {"file": target, "size": target.stat().st_size, "removed": len(removed),
            "media": copy_media(folder) if include_media else "Salin media dilewati."}
