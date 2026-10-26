"""Uang, nomor WA, kode pesanan, filter template, link lacak."""
import pytest
from django.core.exceptions import ValidationError
from django.template import Context, Template
from freezegun import freeze_time

from apps.core.money import format_rupiah
from apps.core.phone import normalize_wa, to_local
from apps.orders.services import codes, links


@pytest.mark.parametrize("amount, text", [
    (1_250_000, "Rp 1.250.000"), (0, "Rp 0"), (500, "Rp 500"), (-1_050_000, "-Rp 1.050.000"),
])
def test_format_rupiah(amount, text):
    assert format_rupiah(amount) == text


def test_filter_rupiah_dan_status():
    html = Template("{% load ui %}{{ v|rupiah }}|{{ s|status_tone }}").render(
        Context({"v": 7500000, "s": "PROSES_WAR"}))
    assert html == "Rp 7.500.000|live"


@pytest.mark.parametrize("raw", ["081234567890", "0812-3456-7890", "+62 812 3456 7890", "6281234567890"])
def test_normalisasi_wa(raw):
    assert normalize_wa(raw) == "6281234567890"
    assert to_local("6281234567890") == "081234567890"


@pytest.mark.parametrize("raw", ["", "12345", "0212345678", "08123", "62712345678", "08abc4567890"])
def test_wa_tidak_valid(raw):
    with pytest.raises(ValidationError):
        normalize_wa(raw)


def test_kode_pesanan():
    code = codes.generate_code()
    assert code.startswith("DRM-") and len(code) == 10
    assert all(ch in codes.ALPHABET for ch in code[4:])
    assert codes.normalize_code("drm-abc234") == "DRM-ABC234"
    assert codes.normalize_code("ABC234") == "DRM-ABC234"


class _O:
    code = "DRM-ABC234"


def test_token_lacak_berlaku_30_hari():
    with freeze_time("2026-10-01"):
        token = links.make_tracking_token(_O())
        assert links.check_tracking_token("DRM-ABC234", token)
        assert not links.check_tracking_token("DRM-ZZZ999", token)  # milik kode lain
        assert not links.check_tracking_token("DRM-ABC234", token + "x")
    with freeze_time("2026-10-30"):
        assert links.check_tracking_token("DRM-ABC234", token)
    with freeze_time("2026-11-01 00:00:01"):
        assert not links.check_tracking_token("DRM-ABC234", token)  # kedaluwarsa
