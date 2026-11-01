"""Moderasi testimoni (docs/05 §11)."""
from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST

from apps.core.enums import TestimonialStatus
from apps.core.forms import StyledFormMixin
from apps.core.uploads import IMAGE_ACCEPT_ATTR
from apps.events.models import Event
from apps.orders.services.transitions import InvalidTransition
from apps.public.lacak_views import serve_private
from apps.testimonials import services as testimonials
from apps.testimonials.models import Testimonial

from .permissions import admin_required
from .views import actor_for, dash_render

TABS = [("menunggu", "Menunggu", TestimonialStatus.MENUNGGU), ("tampil", "Tampil", TestimonialStatus.TAMPIL),
        ("sembunyi", "Disembunyikan", TestimonialStatus.DISEMBUNYIKAN)]
ACTIONS = {
    "setujui": (testimonials.approve, "Testimoni tampil di web."),
    "sembunyikan": (testimonials.hide, "Testimoni disembunyikan."),
    "unggulan": (testimonials.toggle_featured, "Status unggulan diubah."),
}


class ManualForm(StyledFormMixin, forms.Form):
    display_name = forms.CharField(label="Nama tampilan", max_length=80)
    event = forms.ModelChoiceField(label="Event", queryset=Event.objects.all(), required=False, empty_label="Tanpa event")
    rating = forms.TypedChoiceField(label="Rating", coerce=int, initial=5, choices=[(n, f"{n} bintang") for n in range(5, 0, -1)])
    text = forms.CharField(label="Isi", required=False, max_length=1000, widget=forms.Textarea(attrs={"rows": 3}))
    image = forms.ImageField(label="Screenshot chat", required=False,
                             widget=forms.ClearableFileInput(attrs={"accept": IMAGE_ACCEPT_ATTR}))

    def clean(self):
        data = super().clean()
        if not data.get("text") and not data.get("image"):
            raise forms.ValidationError("Isi teks atau unggah screenshot.")
        return data


class EditForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Testimonial
        fields = ["display_name", "text"]
        widgets = {"text": forms.Textarea(attrs={"rows": 3})}


def _back(request):
    return redirect(request.POST.get("next") or reverse("dashboard:testimonials"))


@admin_required
def testimonial_list(request):
    return _render(request)


def _render(request, manual_form=None, status=200):
    tab = request.GET.get("tab", "menunggu")
    current = next((t for t in TABS if t[0] == tab), TABS[0])
    rows = list(Testimonial.objects.filter(status=current[2]).select_related("event", "order"))
    return dash_render(request, "dashboard/testimonials.html", {
        "tabs": [(key, label, Testimonial.objects.filter(status=value).count()) for key, label, value in TABS],
        "tab": current[0], "rows": [(t, EditForm(instance=t, prefix=f"t{t.pk}")) for t in rows],
        "manual_form": manual_form or ManualForm(), "next": request.get_full_path(),
    }, active="testimonials", status=status)


@admin_required
@require_POST
def testimonial_add(request):
    form = ManualForm(request.POST, request.FILES)
    if not form.is_valid():
        return _render(request, manual_form=form, status=422)
    d = form.cleaned_data
    testimonials.create_manual(display_name=d["display_name"], rating=d["rating"], text=d["text"], event=d["event"],
                               image=d["image"], actor=actor_for(request))
    messages.success(request, "Testimoni ditambahkan dan langsung tampil.")
    return redirect(reverse("dashboard:testimonials") + "?tab=tampil")


@admin_required
@require_POST
def testimonial_action(request, pk, action):
    testimonial = get_object_or_404(Testimonial, pk=pk)
    if action not in ACTIONS:
        return _back(request)
    handler, message = ACTIONS[action]
    try:
        handler(testimonial, actor=actor_for(request))
    except InvalidTransition as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, message)
    return _back(request)


@admin_required
@require_POST
def testimonial_edit(request, pk):
    testimonial = get_object_or_404(Testimonial, pk=pk)
    form = EditForm(request.POST, instance=testimonial, prefix=f"t{pk}")
    if form.is_valid():
        testimonials.update_text(testimonial, display_name=form.cleaned_data["display_name"],
                                 text=form.cleaned_data["text"], actor=actor_for(request))
        messages.success(request, "Testimoni diperbarui.")
    else:
        messages.error(request, "Nama tampilan wajib diisi.")
    return _back(request)


@admin_required
@require_POST
def testimonial_delete(request, pk):
    testimonials.delete(get_object_or_404(Testimonial, pk=pk), actor=actor_for(request))
    messages.success(request, "Testimoni dihapus.")
    return _back(request)


@admin_required
def testimonial_image(request, pk):
    """Gambar privat untuk dicek sebelum disetujui."""
    testimonial = get_object_or_404(Testimonial, pk=pk)
    return serve_private(testimonial.image, f"testimoni-{pk}")
