"""
Settings untuk pytest. Memakai MariaDB (DB tes `test_dreamtify_dev`).

DJANGO_TEST_SQLITE=1 → SQLite in-memory, hanya untuk tes logika murni
(docs/11 §1); sebelum fase dianggap selesai tes harus lulus di MariaDB.
"""
import os

from .dev import *  # noqa: F401,F403
from .dev import FIELD_ENCRYPTION_KEYS, NIK_HASH_PEPPER

# Kunci khusus tes bila .env belum ada (mis. CI). Bukan untuk data nyata.
FIELD_ENCRYPTION_KEYS = FIELD_ENCRYPTION_KEYS or ["dGVzdC1rZXktdGVzdC1rZXktdGVzdC1rZXktdGVzdC0="]
NIK_HASH_PEPPER = NIK_HASH_PEPPER or "pepper-khusus-tes"

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

if os.environ.get("DJANGO_TEST_SQLITE") == "1":
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}

# Log tes tidak perlu mengotori logs/app.log
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"null": {"class": "logging.NullHandler"}},
    "root": {"handlers": ["null"]},
}
