"""
Enkripsi field sensitif (docs/09 §1).

- `EncryptedTextField`: disimpan sebagai token Fernet. Kunci dari
  `FIELD_ENCRYPTION_KEYS` (dipisah koma): kunci pertama untuk enkripsi,
  semua untuk dekripsi (MultiFernet → mendukung rotasi kunci).
- `nik_hash()`: HMAC-SHA256 + `NIK_HASH_PEPPER` untuk cek duplikat & cari NIK
  lengkap tanpa mendekripsi.

Field terenkripsi tidak bisa difilter (`filter(holder_nik=...)`); pakai hash.
"""
import hashlib
import hmac
import re
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken, MultiFernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import models

_NON_DIGIT = re.compile(r"\D")


class DecryptionError(Exception):
    """Token tidak bisa didekripsi — kunci salah/hilang. Sengaja gagal keras
    agar data tidak tertimpa kosong tanpa disadari."""


@lru_cache(maxsize=4)
def _multifernet(keys: tuple) -> MultiFernet:
    if not keys:
        raise ImproperlyConfigured(
            "FIELD_ENCRYPTION_KEYS kosong. Isi di .env (jalankan dev.bat / install.bat)."
        )
    try:
        return MultiFernet([Fernet(k.strip().encode()) for k in keys])
    except ValueError as exc:
        raise ImproperlyConfigured("FIELD_ENCRYPTION_KEYS tidak valid (harus kunci Fernet).") from exc


def _fernet() -> MultiFernet:
    return _multifernet(tuple(k for k in settings.FIELD_ENCRYPTION_KEYS if k.strip()))


def encrypt_str(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_str(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError) as exc:
        raise DecryptionError("Data terenkripsi tidak bisa dibaca (cek FIELD_ENCRYPTION_KEYS).") from exc


class EncryptedTextField(models.TextField):
    """TextField yang terenkripsi di database. Nilai kosong ('' / None) tidak dienkripsi."""

    description = "Teks terenkripsi (Fernet)"

    def from_db_value(self, value, expression, connection):
        if value in (None, ""):
            return value
        return decrypt_str(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        if value in (None, ""):
            return value
        return encrypt_str(str(value))


def digits_only(value: str) -> str:
    return _NON_DIGIT.sub("", value or "")


def nik_hash(nik: str) -> str:
    """HMAC-SHA256 (hex) dari NIK yang sudah dibersihkan ke digit saja."""
    pepper = settings.NIK_HASH_PEPPER
    if not pepper:
        raise ImproperlyConfigured("NIK_HASH_PEPPER kosong. Isi di .env.")
    return hmac.new(pepper.encode(), digits_only(nik).encode(), hashlib.sha256).hexdigest()


def mask_nik(last4: str) -> str:
    """Tampilan tersamar: •••• •••• •••• 1234"""
    return f"•••• •••• •••• {last4}" if last4 else ""


def mask_account(number: str) -> str:
    """Nomor rekening tersamar: ••••••7890"""
    digits = digits_only(number)
    return f"••••••{digits[-4:]}" if digits else ""
