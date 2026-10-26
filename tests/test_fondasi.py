"""Tes fase 01: health check, halaman dasar, penyamar log, aset statis."""
import logging
from pathlib import Path

import pytest
from django.conf import settings
from django.db.utils import OperationalError

from apps.core.log_filters import MaskingFormatter, MaskSensitiveFilter, mask_sensitive

STATIC = Path(settings.BASE_DIR) / "static"

# Context processor membaca SiteSetting dari DB
pytestmark = pytest.mark.django_db


# --- /sehat/ ---------------------------------------------------------------

@pytest.mark.django_db
def test_health_ok(client):
    response = client.get("/sehat/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": True}
    assert "no-cache" in response["Cache-Control"]


@pytest.mark.django_db
def test_health_db_down(client, monkeypatch):
    def broken_cursor(*args, **kwargs):
        raise OperationalError(2003, "Can't connect")

    monkeypatch.setattr("apps.core.views.connection.cursor", broken_cursor)
    response = client.get("/sehat/")
    assert response.status_code == 503
    assert response.json() == {"status": "error", "db": False}


def test_health_get_only(client):
    assert client.post("/sehat/").status_code == 405


# --- Halaman --------------------------------------------------------------

def test_home_renders_logo(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.content.decode()
    assert "img/logo-dreamtify-crop.png" in html
    assert 'alt="Dreamtify' in html
    assert '<html lang="id">' in html


def test_home_has_no_inline_script(client):
    """Persiapan CSP (fase 12): tidak ada <script> inline / handler on*=."""
    html = client.get("/").content.decode()
    assert "<script>" not in html
    assert " onclick=" not in html


def test_component_gallery_hidden_in_production(client, settings):
    settings.DEBUG = False
    assert client.get("/_komponen/").status_code == 404
    assert client.get("/_komponen/dashboard/").status_code == 404


def test_component_gallery_in_debug(client, settings):
    settings.DEBUG = True
    response = client.get("/_komponen/")
    assert response.status_code == 200
    html = response.content.decode()
    for marker in ("btn--primary", "btn--secondary", "btn--ghost", "btn--danger",
                   "card--sticker", "badge--live", "toastTrigger", "<dialog", "<details",
                   "copyButton"):
        assert marker in html, marker
    assert client.get("/_komponen/dashboard/").status_code == 200
    # Regresi: parameter "block" bentrok dengan variabel bawaan Django di dalam
    # {% block %} sehingga semua tombol jadi lebar penuh. Hanya satu yang full=True.
    assert html.count("btn--block") == 1


def test_404_page_is_branded(client):
    response = client.get("/halaman-yang-tidak-ada/")
    assert response.status_code == 404
    html = response.content.decode()
    assert "cloud-sad.svg" in html
    assert "Kembali ke beranda" in html


def test_500_template_renders_without_context():
    """500.html dirender Django tanpa context processor; harus tetap aman."""
    from django.template.loader import get_template

    html = get_template("500.html").render()
    assert "Maaf, ada gangguan" in html


# --- Penyamar log -----------------------------------------------------------

@pytest.mark.parametrize("raw", [
    "NIK 3171012345678901 dikirim",
    "NIK 3171 0123 4567 8901 dikirim",
    "NIK 3171-0123-4567-8901 dikirim",
    "rekening 1234567890 atas nama X",
    "WA 6281234567890",
])
def test_mask_sensitive_hides_long_numbers(raw):
    masked = mask_sensitive(raw)
    digits = "".join(ch for ch in raw if ch.isdigit())
    assert digits not in masked.replace(" ", "").replace("-", "")
    assert digits[-4:] in masked


def test_mask_keeps_short_numbers_and_timestamps():
    text = "2026-10-25 14:03:22,123 pesanan DRM-7KX2QP jumlah 4 Rp 750000"
    assert mask_sensitive(text) == text


def test_logging_filter_and_formatter_mask_nik(tmp_path):
    log_file = tmp_path / "app.log"
    logger = logging.getLogger("tes.penyamar")
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.addFilter(MaskSensitiveFilter())
    handler.setFormatter(MaskingFormatter("{levelname} {message}", style="{"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        logger.info("Data pemegang NIK %s", "3171012345678901")
        try:
            raise ValueError("NIK salah: 3171012345678901")
        except ValueError:
            logger.exception("Gagal")
    finally:
        logger.removeHandler(handler)
        handler.close()
    content = log_file.read_text(encoding="utf-8")
    assert "3171012345678901" not in content
    assert "8901" in content


# --- Aset statis (self-host, tanpa CDN) --------------------------------------

@pytest.mark.parametrize("path", [
    "css/tokens.css", "css/base.css", "css/components.css", "css/dashboard.css",
    "fonts/fredoka-latin.woff2", "fonts/nunito-latin.woff2",
    "fonts/OFL-Fredoka.txt", "fonts/OFL-Nunito.txt",
    "js/vendor/htmx.min.js", "js/vendor/alpine-csp.min.js", "js/app.js",
    "img/logo-dreamtify.png", "img/logo-dreamtify-crop.png",
    "img/favicon-32.png", "img/apple-touch-icon.png", "img/icon-512.png", "img/favicon.ico",
    "img/cloud-happy.svg", "img/cloud-sleep.svg", "img/cloud-sad.svg", "img/icons.svg",
])
def test_static_asset_exists(path):
    assert (STATIC / path).is_file(), path


def test_no_cdn_in_templates():
    templates = Path(settings.BASE_DIR) / "templates"
    for file in templates.rglob("*.html"):
        text = file.read_text(encoding="utf-8")
        for host in ("cdn.jsdelivr", "unpkg.com", "fonts.googleapis", "cdnjs", "tailwindcss"):
            assert host not in text, f"{file.name} memuat {host}"


def test_css_budget():
    """docs/06 §6: CSS yang dimuat satu halaman < 60 KB (bersama + CSS khusus halaman terbesar)."""
    css = STATIC / "css"
    shared = sum((css / f).stat().st_size for f in ("tokens.css", "base.css", "components.css"))
    page_specific = max((css / f).stat().st_size for f in ("pages.css", "order.css", "dashboard.css"))
    assert shared + page_specific < 60 * 1024, shared + page_specific
