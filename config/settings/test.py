"""
Settings untuk pytest. Memakai MariaDB (DB tes `test_dreamtify_dev`).

DJANGO_TEST_SQLITE=1 → SQLite in-memory, hanya untuk tes logika murni
(docs/11 §1); sebelum fase dianggap selesai tes harus lulus di MariaDB.
"""
import os

from .dev import *  # noqa: F401,F403

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
