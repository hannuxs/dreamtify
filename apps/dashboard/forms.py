from datetime import timedelta

from django import forms
from django.contrib.auth import get_user_model, password_validation
from django.contrib.auth.forms import AuthenticationForm, SetPasswordForm
from django.core.exceptions import ValidationError
from django.forms import BaseModelFormSet, modelformset_factory

from apps.core.enums import FeeTier, PhaseStatus, ServiceType, TicketPaymentMethod
from apps.core.forms import (
    DATETIME_INPUT_FORMATS,
    DateInput,
    DateTimeLocalInput,
    RupiahField,
    StyledFormMixin,
)
from apps.core.images import process_public_image
from apps.core.models import BankAccount, FaqItem, SiteSetting
from apps.core.phone import normalize_wa
from apps.events.models import Event, SalePhase, TicketCategory

from .permissions import ADMIN, OWNER

User = get_user_model()


class LoginForm(StyledFormMixin, AuthenticationForm):
    error_messages = {
        "invalid_login": "Username atau kata sandi salah.",
        "inactive": "Akun ini dinonaktifkan.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username"
        self.fields["password"].label = "Kata sandi"


# ---------------------------------------------------------------------------
# Event
# ---------------------------------------------------------------------------

class EventInfoForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Event
        fields = ["name", "slug", "artist", "venue", "city", "event_dates", "first_show_date",
                  "ticketing_platform", "description", "poster", "status"]
        widgets = {"first_show_date": DateInput(), "description": forms.Textarea(attrs={"rows": 4})}
        help_texts = {"slug": "Alamat halaman: /event/<slug>/. Kosongkan = dibuat otomatis dari nama."}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["slug"].required = False
        self.fields["poster"].widget = forms.ClearableFileInput(attrs={"accept": "image/jpeg,image/png,image/webp"})

    def clean_poster(self):
        poster = self.cleaned_data.get("poster")
        if poster and hasattr(poster, "content_type"):  # upload baru
            return process_public_image(poster, name="poster")
        return poster


class PhaseForm(StyledFormMixin, forms.ModelForm):
    order_open_at = forms.DateTimeField(label="Pesanan dibuka", required=False, widget=DateTimeLocalInput(),
                                        input_formats=DATETIME_INPUT_FORMATS)
    order_close_at = forms.DateTimeField(label="Pesanan ditutup", required=False, widget=DateTimeLocalInput(),
                                         input_formats=DATETIME_INPUT_FORMATS)
    war_at = forms.DateTimeField(label="Waktu war", required=False, widget=DateTimeLocalInput(),
                                 input_formats=DATETIME_INPUT_FORMATS)
    pelunasan_deadline = forms.DateTimeField(label="Batas pelunasan", required=False, widget=DateTimeLocalInput(),
                                             input_formats=DATETIME_INPUT_FORMATS)

    class Meta:
        model = SalePhase
        fields = ["name", "sort_order", "status", "order_open_at", "order_close_at", "war_at",
                  "pelunasan_deadline", "slot_quota", "membership_required", "membership_label"]

    EDITABLE_STATUSES = [(s.value, s.label) for s in (PhaseStatus.DRAFT, PhaseStatus.BUKA, PhaseStatus.TUTUP)]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = self.EDITABLE_STATUSES
        if self.instance.pk and self.instance.status in (PhaseStatus.WAR, PhaseStatus.SELESAI):
            # Status WAR/SELESAI diatur lewat Mode War
            self.fields["status"].choices = [(self.instance.status, self.instance.get_status_display())]
            self.fields["status"].disabled = True
        self.fields["slot_quota"].widget.attrs.update({"inputmode": "numeric", "placeholder": "Tanpa batas"})

    def clean(self):
        data = super().clean()
        open_at, close_at = data.get("order_open_at"), data.get("order_close_at")
        war_at, deadline = data.get("war_at"), data.get("pelunasan_deadline")
        if open_at and close_at and open_at >= close_at:
            self.add_error("order_close_at", "Harus setelah waktu pesanan dibuka.")
        # ASUMSI D3(a): pesanan harus tutup ≥ 2 jam sebelum war agar sempat bayar fee
        if close_at and war_at and close_at > war_at - timedelta(hours=2):
            self.add_error("order_close_at", "Paling lambat 2 jam sebelum war.")
        if deadline and war_at and deadline > war_at:
            self.add_error("pelunasan_deadline", "Harus sebelum waktu war.")
        if data.get("status") == PhaseStatus.BUKA and not war_at:
            self.add_error("war_at", "Wajib diisi sebelum tahap dibuka.")
        return data


class BasePhaseFormSet(BaseModelFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        names = []
        for form in self.forms:
            if (not form.has_changed() and not form.instance.pk) or self._should_delete_form(form):
                continue
            name = (form.cleaned_data.get("name") or "").strip().lower()
            if name:
                names.append(name)
        if len(names) != len(set(names)):
            raise ValidationError("Nama tahap tidak boleh sama.")


PhaseFormSet = modelformset_factory(SalePhase, form=PhaseForm, formset=BasePhaseFormSet, extra=1, can_delete=True)


class CategoryForm(StyledFormMixin, forms.ModelForm):
    price = RupiahField(label="Harga tiket (Rp)")

    class Meta:
        model = TicketCategory
        fields = ["name", "fee_tier", "price", "sort_order", "is_active", "description"]


CategoryFormSet = modelformset_factory(TicketCategory, form=CategoryForm, extra=2, can_delete=True)


class FeeMatrixForm(StyledFormMixin, forms.Form):
    """Satu sel per (tahap × layanan × tier). Kosong = belum diatur."""

    def __init__(self, *args, event: Event, phases, **kwargs):
        super().__init__(*args, **kwargs)
        self.event = event
        self.phases = list(phases)
        self.services = event.enabled_services() or [s.value for s in ServiceType]
        self.grid = []
        for phase in self.phases:
            existing = {(r.service_type, r.fee_tier): r.fee_per_ticket for r in phase.fee_rules.all()}
            rows = []
            for service in self.services:
                cells = []
                for tier in FeeTier.values:
                    name = f"fee__{phase.pk}__{service}__{tier}"
                    self.fields[name] = RupiahField(required=False, label=f"{phase.name} {service} {tier}",
                                                    initial=existing.get((service, tier)))
                    cells.append(name)
                rows.append((service, cells))
            self.grid.append((phase, rows))

    def bound_grid(self):
        return [(phase, [(service, [self[c] for c in cells]) for service, cells in rows])
                for phase, rows in self.grid]

    def values(self):
        """[(phase, service, tier, nilai|None)]"""
        out = []
        for phase, rows in self.grid:
            for service, cells in rows:
                for name in cells:
                    tier = name.rsplit("__", 1)[1]
                    out.append((phase, service, tier, self.cleaned_data.get(name)))
        return out


class FeeCopyForm(forms.Form):
    source = forms.ModelChoiceField(queryset=SalePhase.objects.none(), label="Salin dari")
    target = forms.ModelChoiceField(queryset=SalePhase.objects.none(), label="ke tahap")

    def __init__(self, *args, event: Event, **kwargs):
        super().__init__(*args, **kwargs)
        qs = event.phases.all()
        self.fields["source"].queryset = qs
        self.fields["target"].queryset = qs
        for f in self.fields.values():
            f.widget.attrs["class"] = "select"

    def clean(self):
        data = super().clean()
        if data.get("source") and data.get("source") == data.get("target"):
            raise ValidationError("Pilih dua tahap yang berbeda.")
        return data


class EventRulesForm(StyledFormMixin, forms.ModelForm):
    payment_methods = forms.MultipleChoiceField(label="Metode bayar tiket", choices=TicketPaymentMethod.choices,
                                                widget=forms.CheckboxSelectMultiple)
    booking_slot_fee = RupiahField(label="Booking slot (Rp/tiket)")
    early_booking_per_ticket = RupiahField(label="Early booking (Rp/tiket)", help_text="0 = tidak ada. Hanya titip bayar.")

    class Meta:
        model = Event
        fields = ["jaswar_enabled", "jastip_enabled", "payment_methods", "max_lines_per_order",
                  "max_tickets_per_holder", "required_backups", "fee_basis", "booking_slot_fee",
                  "early_booking_per_ticket", "fee_payment_window_hours", "late_pelunasan_policy",
                  "unique_code_enabled", "customer_va_enabled", "fallback_any_category", "terms",
                  "redemption_info"]
        widgets = {"terms": forms.Textarea(attrs={"rows": 5}), "redemption_info": forms.Textarea(attrs={"rows": 4})}

    def clean(self):
        data = super().clean()
        if not data.get("jaswar_enabled") and not data.get("jastip_enabled"):
            raise ValidationError("Aktifkan minimal satu layanan (JASWAR atau JASTIP).")
        return data


class PromotorForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Event
        fields = ["promotor_name", "promotor_link_enabled", "promotor_include_nik"]

    def __init__(self, *args, owner: bool, **kwargs):
        super().__init__(*args, **kwargs)
        if not owner:
            self.fields["promotor_include_nik"].disabled = True
            self.fields["promotor_include_nik"].help_text = "Hanya Owner yang bisa mengubah."


# ---------------------------------------------------------------------------
# Pengaturan (Owner)
# ---------------------------------------------------------------------------

class SiteBrandForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = ["brand_name", "tagline", "admin_whatsapp", "instagram", "contact_email"]
        help_texts = {"admin_whatsapp": "Tujuan tombol \"Tanya admin\". Contoh: 0812 3456 7890."}

    def clean_admin_whatsapp(self):
        value = self.cleaned_data.get("admin_whatsapp")
        return normalize_wa(value) if value else ""

    def clean_instagram(self):
        return (self.cleaned_data.get("instagram") or "").strip().lstrip("@")


class SiteTermsForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SiteSetting
        fields = ["refund_policy_summary", "general_terms", "privacy_policy"]
        widgets = {f: forms.Textarea(attrs={"rows": 8}) for f in ("general_terms", "privacy_policy")}


class SiteRulesForm(StyledFormMixin, forms.ModelForm):
    default_booking_slot_fee = RupiahField(label="Booking slot default (Rp/tiket)")

    class Meta:
        model = SiteSetting
        fields = ["default_fee_payment_window_hours", "default_booking_slot_fee",
                  "sensitive_data_retention_days", "email_notifications_enabled"]


class BankAccountForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = BankAccount
        fields = ["bank_name", "account_number", "account_holder", "note", "sort_order", "is_active"]


BankAccountFormSet = modelformset_factory(BankAccount, form=BankAccountForm, extra=1, can_delete=True)


class FaqForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = FaqItem
        fields = ["question", "answer", "sort_order", "is_active"]
        widgets = {"answer": forms.Textarea(attrs={"rows": 3})}


FaqFormSet = modelformset_factory(FaqItem, form=FaqForm, extra=1, can_delete=True)


# ---------------------------------------------------------------------------
# Pengguna (Owner)
# ---------------------------------------------------------------------------

ROLE_CHOICES = [(ADMIN, "Admin — operasional"), (OWNER, "Owner — semua akses")]


class UserCreateForm(StyledFormMixin, forms.ModelForm):
    role = forms.ChoiceField(label="Peran", choices=ROLE_CHOICES, initial=ADMIN)
    password1 = forms.CharField(label="Kata sandi", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))
    password2 = forms.CharField(label="Ulangi kata sandi", widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}))

    class Meta:
        model = User
        fields = ["username", "first_name", "email"]
        labels = {"first_name": "Nama"}

    def clean(self):
        data = super().clean()
        p1, p2 = data.get("password1"), data.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Kata sandi tidak sama.")
        elif p1:
            try:
                password_validation.validate_password(p1, self.instance)
            except ValidationError as exc:
                self.add_error("password1", exc)
        return data


class UserEditForm(StyledFormMixin, forms.ModelForm):
    role = forms.ChoiceField(label="Peran", choices=ROLE_CHOICES)

    class Meta:
        model = User
        fields = ["first_name", "email", "is_active"]
        labels = {"first_name": "Nama", "is_active": "Aktif (bisa masuk)"}


class StyledSetPasswordForm(StyledFormMixin, SetPasswordForm):
    pass


class AuditFilterForm(StyledFormMixin, forms.Form):
    q = forms.CharField(label="Cari", required=False,
                        widget=forms.TextInput(attrs={"placeholder": "Kode pesanan, pengguna, ringkasan…"}))
    action = forms.ChoiceField(label="Aksi", required=False)
    date_from = forms.DateField(label="Dari", required=False, widget=DateInput())
    date_to = forms.DateField(label="Sampai", required=False, widget=DateInput())

    def __init__(self, *args, actions=(), **kwargs):
        super().__init__(*args, **kwargs)
        actions = list(actions)
        requested = (self.data.get("action") or "").strip()
        if requested and requested not in actions:
            actions.append(requested)  # filter tetap berlaku walau belum ada log aksi itu
        self.fields["action"].choices = [("", "Semua aksi")] + [(a, a) for a in actions]
