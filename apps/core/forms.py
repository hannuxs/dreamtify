"""Dasar form: kelas CSS komponen, atribut aksesibilitas error, field rupiah."""
import re

from django import forms

_NON_DIGIT = re.compile(r"\D")


class StyledFormMixin:
    """Beri kelas CSS sesuai jenis widget + aria-invalid/aria-describedby saat error."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            widget = field.widget
            if isinstance(widget, (forms.CheckboxInput, forms.RadioSelect, forms.CheckboxSelectMultiple,
                                   forms.HiddenInput, forms.FileInput)):
                continue
            css = "select" if isinstance(widget, forms.Select) else (
                "textarea" if isinstance(widget, forms.Textarea) else "input")
            widget.attrs["class"] = f"{css} {widget.attrs.get('class', '')}".strip()

    def full_clean(self):
        super().full_clean()
        for name in self.errors:
            if name in self.fields:
                attrs = self.fields[name].widget.attrs
                attrs["aria-invalid"] = "true"
                attrs["aria-describedby"] = f"{self.add_prefix(name)}-error"


def format_thousands(value) -> str:
    if value in (None, ""):
        return ""
    try:
        return f"{int(value):,}".replace(",", ".")
    except (TypeError, ValueError):
        return str(value)


class RupiahInput(forms.TextInput):
    """Input angka dengan pemisah ribuan saat ditampilkan (Alpine `moneyInput` memformat saat mengetik)."""

    def __init__(self, attrs=None):
        base = {"inputmode": "numeric", "autocomplete": "off", "x-data": "moneyInput", "@input": "format",
                "class": "money"}
        base.update(attrs or {})
        super().__init__(base)

    def format_value(self, value):
        return format_thousands(value)


class RupiahField(forms.IntegerField):
    """Nominal rupiah: menerima '3.500.000' / 'Rp 3,500,000' → 3500000 (integer)."""

    widget = RupiahInput

    def __init__(self, **kwargs):
        kwargs.setdefault("min_value", 0)
        super().__init__(**kwargs)

    def to_python(self, value):
        if isinstance(value, str):
            value = _NON_DIGIT.sub("", value)
        return super().to_python(value)


class DateTimeLocalInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%dT%H:%M")


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, attrs=None):
        super().__init__(attrs=attrs, format="%Y-%m-%d")


DATETIME_INPUT_FORMATS = ["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"]
