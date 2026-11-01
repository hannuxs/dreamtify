"""Server produksi waitress (dipanggil prod.bat). Log ke logs/web.log, rotasi harian, simpan 14 hari."""
import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from waitress import serve

from config.wsgi import application

logger = logging.getLogger("waitress")


class Command(BaseCommand):
    help = "Jalankan web produksi dengan waitress."

    def handle(self, *args, **options):
        logger.info("Dreamtify berjalan di %s:%s (%s thread)", settings.WEB_HOST, settings.WEB_PORT,
                    settings.WAITRESS_THREADS)
        serve(application, host=settings.WEB_HOST, port=settings.WEB_PORT, threads=settings.WAITRESS_THREADS,
              url_scheme="http", ident="Dreamtify")
