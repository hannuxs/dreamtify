"""Halaman khusus Owner: Pengaturan, Pengguna, Log aktivitas (docs/05 §12–13)."""
from datetime import datetime, time

from django.contrib.auth import get_user_model, update_session_auth_hash
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone

from apps.core import audit
from apps.core.models import AuditLog, BankAccount, FaqItem, SiteSetting
from apps.notifications.defaults import DEFAULT_TEMPLATES
from apps.notifications.models import MessageTemplate
from apps.notifications.services import unknown_placeholders

from .forms import (
    AuditFilterForm,
    BankAccountFormSet,
    FaqFormSet,
    SiteBrandForm,
    SiteRulesForm,
    SiteTermsForm,
    StyledSetPasswordForm,
    UserCreateForm,
    UserEditForm,
)
from .permissions import ADMIN, OWNER, owner_required, role_of
from .views import actor_for, dash_render, saved

User = get_user_model()

SETTING_TABS = [
    ("brand", "Brand & kontak"),
    ("rekening", "Rekening"),
    ("syarat", "Syarat & privasi"),
    ("faq", "FAQ"),
    ("aturan", "Aturan default"),
    ("template", "Template pesan"),
]


# ---------------------------------------------------------------------------
# Pengaturan
# ---------------------------------------------------------------------------

def _setting_forms(request, tab, bound):
    data = request.POST if bound else None
    site = SiteSetting.load()
    if tab == "brand":
        return {"form": SiteBrandForm(data, instance=site)}
    if tab == "syarat":
        return {"form": SiteTermsForm(data, instance=site)}
    if tab == "aturan":
        return {"form": SiteRulesForm(data, instance=site)}
    if tab == "rekening":
        return {"formset": BankAccountFormSet(data, queryset=BankAccount.objects.all(), prefix="bank")}
    if tab == "faq":
        return {"formset": FaqFormSet(data, queryset=FaqItem.objects.all(), prefix="faq")}
    if tab == "template":
        saved = {tpl.key: tpl for tpl in MessageTemplate.objects.all()}
        rows = []
        for key, (title, body, _) in DEFAULT_TEMPLATES.items():
            tpl = saved.get(key)
            rows.append({"key": key, "title": tpl.title if tpl else title, "active": tpl.is_active if tpl else True,
                         "customized": bool(tpl and tpl.is_customized),
                         "unknown": unknown_placeholders(tpl.body if tpl else body)})
        return {"templates": rows}
    return {}


@owner_required
def settings_page(request, tab="brand"):
    if tab not in dict(SETTING_TABS):
        raise Http404
    bound = request.method == "POST" and tab != "template"
    ctx = _setting_forms(request, tab, bound)

    def render_page(context, toast=None):
        return dash_render(request, "dashboard/settings.html", {"tab": tab, "tabs": SETTING_TABS, **context},
                           active="settings", toast=toast)

    if bound:
        target = ctx.get("form") or ctx.get("formset")
        if target.is_valid():
            with transaction.atomic():
                target.save()
                audit.log("settings.update", actor=actor_for(request),
                          summary=f"Pengaturan diubah: {dict(SETTING_TABS)[tab]}")
            return saved(request, "Pengaturan tersimpan.", reverse("dashboard:settings_tab", args=[tab]),
                         lambda msg: render_page(_setting_forms(request, tab, False), toast=msg))
    return render_page(ctx)


# ---------------------------------------------------------------------------
# Pengguna
# ---------------------------------------------------------------------------

def _set_role(user, role):
    owner, _ = Group.objects.get_or_create(name=OWNER)
    admin, _ = Group.objects.get_or_create(name=ADMIN)
    user.groups.remove(owner, admin)
    user.groups.add(owner if role == OWNER else admin)
    user._dt_role = "unset"


def _active_owner_count(exclude_pk=None) -> int:
    qs = User.objects.filter(is_active=True).filter(Q(is_superuser=True) | Q(groups__name=OWNER)).distinct()
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    return qs.count()


@owner_required
def user_list(request):
    users = (User.objects.filter(Q(is_superuser=True) | Q(groups__name__in=(OWNER, ADMIN)))
             .distinct().order_by("-is_active", "username"))
    rows = [{"user": u, "role": role_of(u) or "-"} for u in users]
    return dash_render(request, "dashboard/users/list.html", {"rows": rows}, active="users")


@owner_required
def user_create(request):
    form = UserCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save(commit=False)
            user.is_staff = True
            user.set_password(form.cleaned_data["password1"])
            user.save()
            _set_role(user, form.cleaned_data["role"])
            audit.log("user.create", actor=actor_for(request), obj=user,
                      summary=f"Pengguna baru {user.username} ({form.cleaned_data['role']})")
        return saved(request, f"Pengguna {user.username} dibuat.", reverse("dashboard:user_list"), None)
    return dash_render(request, "dashboard/users/form.html", {"form": form, "creating": True}, active="users")


@owner_required
def user_edit(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = UserEditForm(request.POST or None, instance=user, initial={"role": role_of(user) or ADMIN})
    if request.method == "POST" and form.is_valid():
        demote = form.cleaned_data["role"] != OWNER or not form.cleaned_data["is_active"]
        if demote and role_of(user) == OWNER and _active_owner_count(exclude_pk=user.pk) == 0:
            form.add_error(None, "Harus ada minimal satu Owner aktif.")
        elif user.pk == request.user.pk and demote:
            form.add_error(None, "Kamu tidak bisa menurunkan peran / menonaktifkan akunmu sendiri.")
        else:
            with transaction.atomic():
                form.save()
                if not user.is_superuser:
                    _set_role(user, form.cleaned_data["role"])
                audit.log("user.update", actor=actor_for(request), obj=user,
                          summary=f"Pengguna {user.username} diubah: {', '.join(form.changed_data) or 'tanpa perubahan'}")
            return saved(request, "Pengguna tersimpan.", reverse("dashboard:user_list"), None)
    return dash_render(request, "dashboard/users/form.html", {"form": form, "target": user}, active="users")


@owner_required
def user_password(request, pk):
    user = get_object_or_404(User, pk=pk)
    form = StyledSetPasswordForm(user, request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        if user.pk == request.user.pk:
            update_session_auth_hash(request, user)
        audit.log("user.password_reset", actor=actor_for(request), obj=user,
                  summary=f"Kata sandi {user.username} diganti")
        return saved(request, f"Kata sandi {user.username} diganti.", reverse("dashboard:user_list"), None)
    return dash_render(request, "dashboard/users/password.html", {"form": form, "target": user}, active="users")


# ---------------------------------------------------------------------------
# Log aktivitas
# ---------------------------------------------------------------------------

@owner_required
def audit_log(request):
    actions = AuditLog.objects.order_by("action").values_list("action", flat=True).distinct()
    form = AuditFilterForm(request.GET or None, actions=list(actions))
    logs = AuditLog.objects.select_related("actor")
    if form.is_valid():
        d = form.cleaned_data
        if d["q"]:
            logs = logs.filter(Q(summary__icontains=d["q"]) | Q(actor_label__icontains=d["q"])
                               | Q(object_id=d["q"]) | Q(action__icontains=d["q"]))
        if d["action"]:
            logs = logs.filter(action=d["action"])
        tz = timezone.get_current_timezone()
        # Rentang waktu (bukan __date) agar tidak bergantung pada CONVERT_TZ di DB
        if d["date_from"]:
            logs = logs.filter(created_at__gte=timezone.make_aware(datetime.combine(d["date_from"], time.min), tz))
        if d["date_to"]:
            logs = logs.filter(created_at__lte=timezone.make_aware(datetime.combine(d["date_to"], time.max), tz))
    page = Paginator(logs, 50).get_page(request.GET.get("page"))
    query = request.GET.copy()
    query.pop("page", None)
    return dash_render(request, "dashboard/audit_log.html", {
        "form": form, "page": page, "query": query.urlencode(),
    }, active="log")


def redirect_settings(request):
    return redirect("dashboard:settings_tab", tab="brand")
