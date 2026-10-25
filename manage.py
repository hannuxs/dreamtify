#!/usr/bin/env python
"""Utilitas baris perintah Django untuk Dreamtify."""
import os
import sys


def main():
    # DJANGO_ENV (dev/prod) di-set oleh dev.bat / prod.bat; default dev.
    env = os.environ.get("DJANGO_ENV", "dev")
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", f"config.settings.{env}")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django belum terpasang. Jalankan dev.bat atau install.bat dulu."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
