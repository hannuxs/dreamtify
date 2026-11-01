"""
Settings bersama Dreamtify. Nilai dibaca dari file `.env` (django-environ).

Modul dev.py / prod.py / test.py mengimpor file ini lalu menimpa seperlunya.
`DJANGO_ENV` (dev/prod) dipilih oleh manage.py / wsgi.py.
"""
import os
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DJANGO_ENV = os.environ.get("DJANGO_ENV", "dev")

env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# ---------------------------------------------------------------------------
# Umum
# ---------------------------------------------------------------------------
SECRET_KEY = env("SECRET_KEY", default="")
DEBUG = False
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])
SITE_URL = env("SITE_URL", default="http://localhost:8383").rstrip("/")
HTTPS = env.bool("HTTPS", default=False)
TRUSTED_PROXY = env.bool("TRUSTED_PROXY", default=False)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    # Aplikasi Dreamtify
    "apps.core",
    "apps.events",
    "apps.orders",
    "apps.notifications",
    "apps.testimonials",
    "apps.exports",
    "apps.public",
    "apps.dashboard",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.core.middleware.SecurityHeadersMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "apps.dashboard.middleware.AdminIdleTimeoutMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "apps.core.context_processors.site",
            ],
        },
    },
]

# ---------------------------------------------------------------------------
# Database — MariaDB port 3309, utf8mb4
# ---------------------------------------------------------------------------
DB_DRIVER = env("DB_DRIVER", default="mysqlclient").lower()
if DB_DRIVER == "pymysql":
    import pymysql

    pymysql.install_as_MySQLdb()

DB_NAME = env("DB_NAME_DEV" if DJANGO_ENV == "dev" else "DB_NAME",
              default="dreamtify_dev" if DJANGO_ENV == "dev" else "dreamtify")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": DB_NAME,
        "USER": env("DB_USER", default="dreamtify"),
        "PASSWORD": env("DB_PASSWORD", default=""),
        "HOST": env("DB_HOST", default="127.0.0.1"),
        "PORT": env("DB_PORT", default="3309"),
        "CONN_MAX_AGE": 60,
        "CONN_HEALTH_CHECKS": True,
        "OPTIONS": {
            "charset": "utf8mb4",
            "init_command": (
                "SET sql_mode='STRICT_TRANS_TABLES,NO_ZERO_DATE,"
                "NO_ZERO_IN_DATE,ERROR_FOR_DIVISION_BY_ZERO'"
            ),
        },
        "TEST": {
            "NAME": f"test_{DB_NAME}",
            "CHARSET": "utf8mb4",
            "COLLATION": "utf8mb4_unicode_ci",
        },
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Cache (juga untuk rate limit) — tanpa Redis
# ---------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "django_cache",
    }
}

# ---------------------------------------------------------------------------
# Autentikasi
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 10}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "/kelola/login/"
LOGIN_REDIRECT_URL = "/kelola/"
# Sesi: admin di-set 8 jam saat login (+ logout bila tidak aktif 2 jam, lihat
# apps/dashboard/middleware.py). Akses lacak customer 12 jam (fase 05).
SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"

# ---------------------------------------------------------------------------
# Bahasa & waktu — simpan UTC, tampilkan WIB
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "id"
LANGUAGES = [("id", "Bahasa Indonesia")]
TIME_ZONE = env("TIME_ZONE", default="Asia/Jakarta")
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# File statis & media
# ---------------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"
STATIC_ROOT.mkdir(exist_ok=True)  # whitenoise memperingatkan bila folder belum ada
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

MEDIA_ROOT = BASE_DIR / "media"
# File privat & publik disajikan lewat view berizin (docs/09 §4), bukan MEDIA_URL.
MEDIA_URL = "/media/"
PRIVATE_MEDIA_ROOT = MEDIA_ROOT / "private"
PUBLIC_MEDIA_ROOT = MEDIA_ROOT / "public"
FILE_UPLOAD_MAX_MEMORY_SIZE = 2.5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 12 * 1024 * 1024

# ---------------------------------------------------------------------------
# Email (opsional)
# ---------------------------------------------------------------------------
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Dreamtify <noreply@localhost>")
EMAIL_BACKEND = (
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST
    else "django.core.mail.backends.console.EmailBackend"
)

# ---------------------------------------------------------------------------
# Keamanan data (dipakai mulai fase 02)
# ---------------------------------------------------------------------------
FIELD_ENCRYPTION_KEYS = env.list("FIELD_ENCRYPTION_KEYS", default=[])
NIK_HASH_PEPPER = env("NIK_HASH_PEPPER", default="")

# ---------------------------------------------------------------------------
# Header keamanan (CSP & Permissions-Policy di apps.core.middleware)
# ---------------------------------------------------------------------------
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
# Browser mengabaikan & memperingatkan header ini di HTTP polos
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin" if HTTPS else None

# ---------------------------------------------------------------------------
# Logging — ke logs/, dengan penyamar NIK / nomor panjang (docs/09 §2)
# ---------------------------------------------------------------------------
# Backup (docs/09 §9)
BACKUP_DIR = BASE_DIR / env("BACKUP_DIR", default="backups")
BACKUP_KEEP = env.int("BACKUP_KEEP", default=14)
MARIADB_BIN = env("MARIADB_BIN", default="")

LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "mask_sensitive": {"()": "apps.core.log_filters.MaskSensitiveFilter"},
    },
    "formatters": {
        "masked": {
            "()": "apps.core.log_filters.MaskingFormatter",
            "fmt": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["mask_sensitive"],
            "formatter": "masked",
        },
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "app.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 10,
            "encoding": "utf-8",
            # delay: proses autoreloader runserver tidak ikut mengunci file (Windows)
            "delay": True,
            "filters": ["mask_sensitive"],
            "formatter": "masked",
        },
        "daily": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "daily.log",
            "maxBytes": 1024 * 1024,
            "backupCount": 5,
            "encoding": "utf-8",
            "delay": True,
            "filters": ["mask_sensitive"],
            "formatter": "masked",
        },
    },
    "root": {"handlers": ["console", "file"], "level": "INFO"},
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
        "django.db.backends": {"level": "WARNING"},
        "dreamtify.daily": {"handlers": ["console", "daily"], "level": "INFO", "propagate": False},
    },
}
