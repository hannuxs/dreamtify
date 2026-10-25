"""Settings mode pengembangan (dev.bat)."""
from .base import *  # noqa: F401,F403
from .base import SECRET_KEY

DEBUG = True
# Bisa dibuka dari HP di jaringan yang sama (runserver 0.0.0.0:8383)
ALLOWED_HOSTS = ["*"]

SECRET_KEY = SECRET_KEY or "dev-only-insecure-key-ganti-di-env"

INTERNAL_IPS = ["127.0.0.1"]
