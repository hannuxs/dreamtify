"""
Form pesanan publik (docs/04 §3). Validasi ramah per field di sini; aturan
bisnis final tetap dijaga `orders.services` (validation.py).
"""
from django import forms
from django.core.exceptions import ValidationError

from apps.core.crypto import digits_only
from apps.core.enums import Gender, ServiceType, TicketPaymentMethod
from apps.core.forms import DateInput, StyledFormMixin
from apps.core.phone import normalize_wa
from apps.core.money import format_rupiah

WA_ATTRS = {"inputmode": "tel", "autocomplete": "tel", "placeholder": "0812 3456 7890",
            "pattern": r"[0-9+\s\-]{9,20}"}


class NoValueTextInput(forms.TextInput):
    """Tidak pernah merender ulang nilainya (NIK tidak boleh tampil utuh setelah dikirim)."""

    def format_value(self, value):
        return None


class BuyerForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label="Nama lengkap", max_length=150,
                           widget=forms.TextInput(attrs={"autocomplete": "name"}))
    whatsapp = forms.CharField(label="No. WhatsApp", max_length=20, widget=forms.TextInput(attrs=WA_ATTRS),
                               help_text="Untuk kabar pesanan & masuk halaman lacak.")
    email = forms.EmailField(label="Email", widget=forms.EmailInput(attrs={"autocomplete": "email"}))
    instagram = forms.CharField(label="Username IG", max_length=64,
                                widget=forms.TextInput(attrs={"placeholder": "@username", "autocapitalize": "off"}))
    referral = forms.CharField(label="No WA / IG yang merekomendasikan Dreamtify", max_length=150, required=False,
                               help_text="Opsional.")

    def clean_whatsapp(self):
        return normalize_wa(self.cleaned_data["whatsapp"])

    def clean_instagram(self):
        return self.cleaned_data["instagram"].strip().lstrip("@")


class LineForm(StyledFormMixin, forms.Form):
    service_type = forms.ChoiceField(label="Layanan", widget=forms.RadioSelect)
    quantity = forms.IntegerField(label="Jumlah tiket", min_value=1)
    primary = forms.TypedChoiceField(label="Kategori utama", coerce=int)
    backup1 = forms.TypedChoiceField(label="Cadangan 1", coerce=int, required=False, empty_value=None)
    backup2 = forms.TypedChoiceField(label="Cadangan 2", coerce=int, required=False, empty_value=None)

    holder_name = forms.CharField(label="Nama lengkap (sesuai KTP)", max_length=150)
    holder_whatsapp = forms.CharField(label="No. WhatsApp", max_length=20, widget=forms.TextInput(attrs=WA_ATTRS))
    holder_nik = forms.CharField(label="No. KTP (NIK)", required=False, max_length=24, widget=NoValueTextInput(
        attrs={"inputmode": "numeric", "autocomplete": "off", "pattern": r"[0-9\s]{16,19}",
               "placeholder": "16 digit", "required": True}))
    holder_gender = forms.ChoiceField(label="Jenis kelamin", required=False, choices=Gender.choices,
                                      widget=forms.RadioSelect(attrs={"required": True}))
    holder_birth_date = forms.DateField(label="Tanggal lahir", required=False, widget=DateInput(attrs={"required": True}))
    holder_email = forms.EmailField(label="Email", required=False,
                                    widget=forms.EmailInput(attrs={"required": True, "autocomplete": "off"}))
    holder_instagram = forms.CharField(label="Username IG", required=False, max_length=64,
                                       widget=forms.TextInput(attrs={"required": True, "placeholder": "@username",
                                                                     "autocapitalize": "off"}))
    holder_membership_no = forms.CharField(label="No. membership", required=False, max_length=64,
                                           widget=forms.TextInput(attrs={"required": True, "autocomplete": "off"}))
    same_as_buyer = forms.BooleanField(label="Pemegang tiket = saya (pemesan)", required=False)

    def __init__(self, *args, event, phase, categories, **kwargs):
        super().__init__(*args, **kwargs)
        self.event, self.phase = event, phase
        self.fields["service_type"].choices = [(s, s) for s in event.enabled_services()]
        self.fields["quantity"].widget.attrs.update({"min": 1, "max": event.max_tickets_per_holder})
        options = [("", "Pilih kategori")] + [
            (c.pk, f"{c.name} — {format_rupiah(c.price)} · {c.get_fee_tier_display()}") for c in categories]
        for name in ("primary", "backup1", "backup2"):
            self.fields[name].choices = options
            self.fields[name].widget.attrs.update({"class": "select js-cat", "@change": "pickCategory"})
        for n in (1, 2):
            if n <= event.required_backups:
                self.fields[f"backup{n}"].required = True
                self.fields[f"backup{n}"].widget.attrs["required"] = True
        self.membership_required = phase.membership_required
        if phase.membership_label:
            self.fields["holder_membership_no"].label = phase.membership_label

    def clean_holder_whatsapp(self):
        return normalize_wa(self.cleaned_data["holder_whatsapp"])

    def clean_quantity(self):
        qty = self.cleaned_data["quantity"]
        if qty > self.event.max_tickets_per_holder:
            raise ValidationError(f"Maksimal {self.event.max_tickets_per_holder} tiket per pemegang.")
        return qty

    def clean(self):
        data = super().clean()
        cats = [data.get(k) for k in ("primary", "backup1", "backup2") if data.get(k)]
        if len(cats) != len(set(cats)):
            self.add_error("backup1", "Kategori utama, cadangan 1, dan cadangan 2 harus berbeda.")
        if data.get("service_type") == ServiceType.JASWAR:
            nik = digits_only(data.get("holder_nik"))
            if len(nik) != 16:
                self.add_error("holder_nik", "No. KTP (NIK) harus 16 digit.")
            data["holder_nik"] = nik
            for field, message in (("holder_gender", "Pilih jenis kelamin."),
                                   ("holder_birth_date", "Tanggal lahir wajib diisi."),
                                   ("holder_email", "Email wajib diisi."),
                                   ("holder_instagram", "Username IG wajib diisi.")):
                if not data.get(field) and field not in self.errors:
                    self.add_error(field, message)
            if self.membership_required and not (data.get("holder_membership_no") or "").strip():
                self.add_error("holder_membership_no", "No. membership wajib untuk tahap ini.")
        else:
            # JASTIP memakai data tim: data identitas tidak disimpan (ASUMSI C2)
            for field in ("holder_nik", "holder_gender", "holder_birth_date", "holder_email",
                          "holder_instagram", "holder_membership_no"):
                data[field] = None if field == "holder_birth_date" else ""
        return data


class PaymentForm(StyledFormMixin, forms.Form):
    payment_method = forms.ChoiceField(label="Metode bayar tiket", widget=forms.RadioSelect)

    def __init__(self, *args, event, **kwargs):
        super().__init__(*args, **kwargs)
        labels = dict(TicketPaymentMethod.choices)
        self.fields["payment_method"].choices = [(m, labels.get(m, m)) for m in event.payment_methods]


class AgreeForm(StyledFormMixin, forms.Form):
    agree_terms = forms.BooleanField(label="Saya sudah membaca & setuju dengan syarat event dan syarat umum Dreamtify.")
    agree_privacy = forms.BooleanField(label="Saya setuju data KTP dipakai untuk pembelian tiket dan dihapus setelah event selesai.")
