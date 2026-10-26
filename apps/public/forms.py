"""
Form pesanan publik (docs/04 §3). Validasi ramah per field di sini; aturan
bisnis final tetap dijaga `orders.services` (validation.py).
"""
from django import forms
from django.core.exceptions import ValidationError

from apps.core.crypto import digits_only
from apps.core.enums import Gender, ServiceType, TicketPaymentMethod
from apps.core.forms import DATETIME_INPUT_FORMATS, DateInput, DateTimeLocalInput, RupiahField, StyledFormMixin
from apps.core.models import BankAccount
from apps.core.phone import normalize_wa
from apps.core.uploads import ACCEPT_ATTR, process_private_upload
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


# ---------------------------------------------------------------------------
# Lacak pesanan (docs/04 §5)
# ---------------------------------------------------------------------------

class TrackLoginForm(StyledFormMixin, forms.Form):
    code = forms.CharField(label="Kode pesanan", max_length=16,
                           widget=forms.TextInput(attrs={"placeholder": "DRM-XXXXXX", "autocapitalize": "characters",
                                                         "autocomplete": "off", "spellcheck": "false"}))
    whatsapp = forms.CharField(label="No. WhatsApp pemesan", max_length=20, widget=forms.TextInput(attrs=WA_ATTRS))


class PaymentUploadForm(StyledFormMixin, forms.Form):
    amount = RupiahField(label="Nominal yang ditransfer (Rp)")
    sender_name = forms.CharField(label="Nama pengirim (sesuai rekening)", max_length=150)
    sender_bank = forms.CharField(label="Bank / e-wallet pengirim", max_length=50,
                                  widget=forms.TextInput(attrs={"placeholder": "BCA, Mandiri, DANA, …"}))
    transfer_date = forms.DateField(label="Tanggal transfer", widget=DateInput())
    destination_account = forms.ModelChoiceField(label="Ditransfer ke rekening", queryset=None, required=False,
                                                 empty_label="Pilih rekening tujuan")
    proof = forms.FileField(label="Bukti transfer", widget=forms.ClearableFileInput(attrs={"accept": ACCEPT_ATTR}),
                            help_text="Foto/screenshot (JPG, PNG, WEBP) atau PDF, maks 10 MB.")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        accounts = BankAccount.objects.filter(is_active=True)
        self.fields["destination_account"].queryset = accounts
        if len(accounts) == 1:
            self.fields["destination_account"].initial = accounts[0].pk

    def clean_amount(self):
        amount = self.cleaned_data["amount"]
        if not amount:
            raise ValidationError("Nominal transfer wajib diisi.")
        return amount

    def clean_proof(self):
        return process_private_upload(self.cleaned_data["proof"], name="bukti")


class RefundAccountForm(StyledFormMixin, forms.Form):
    bank = forms.CharField(label="Bank / e-wallet", max_length=50)
    number = forms.CharField(label="Nomor rekening", max_length=30,
                             widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}))
    holder = forms.CharField(label="Atas nama", max_length=120)


class HolderEditForm(StyledFormMixin, forms.Form):
    name = forms.CharField(label="Nama lengkap (sesuai KTP)", max_length=150)
    whatsapp = forms.CharField(label="No. WhatsApp", max_length=20, widget=forms.TextInput(attrs=WA_ATTRS))
    nik = forms.CharField(label="No. KTP (NIK) baru", required=False, max_length=24, widget=NoValueTextInput(
        attrs={"inputmode": "numeric", "autocomplete": "off", "pattern": r"[0-9\s]{16,19}"}),
        help_text="Kosongkan bila tidak berubah.")
    gender = forms.ChoiceField(label="Jenis kelamin", required=False, choices=Gender.choices, widget=forms.RadioSelect)
    birth_date = forms.DateField(label="Tanggal lahir", required=False, widget=DateInput())
    email = forms.EmailField(label="Email", required=False)
    instagram = forms.CharField(label="Username IG", required=False, max_length=64)
    membership_no = forms.CharField(label="No. membership", required=False, max_length=64)
    reason = forms.CharField(label="Alasan koreksi", required=False, max_length=200,
                             help_text="Wajib bila pesanan sudah masuk war.")

    def __init__(self, *args, line, after_war=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.line = line
        if line.service_type != ServiceType.JASWAR:
            for name in ("nik", "gender", "birth_date", "email", "instagram", "membership_no"):
                del self.fields[name]
        elif not line.order.phase.membership_required:
            del self.fields["membership_no"]
        if line.holder_nik_last4 and "nik" in self.fields:
            self.fields["nik"].help_text = f"Saat ini •••• {line.holder_nik_last4}. Kosongkan bila tidak berubah."
        if not after_war:
            del self.fields["reason"]


class CustomerVaForm(StyledFormMixin, forms.Form):
    """VA hasil war mandiri yang dikirim customer titip bayar (docs/02 §8.4)."""

    bank = forms.CharField(label="Bank VA", max_length=50)
    va_number = forms.CharField(label="Nomor VA", max_length=64, widget=forms.TextInput(attrs={"inputmode": "numeric"}))
    amount = RupiahField(label="Nominal (Rp)")
    expires_at = forms.DateTimeField(label="Bayar sebelum", required=False, widget=DateTimeLocalInput(),
                                     input_formats=DATETIME_INPUT_FORMATS)
    screenshot = forms.FileField(label="Screenshot VA (opsional)", required=False,
                                 widget=forms.ClearableFileInput(attrs={"accept": ACCEPT_ATTR}))

    def clean_screenshot(self):
        shot = self.cleaned_data.get("screenshot")
        return process_private_upload(shot, name="va") if shot else None
