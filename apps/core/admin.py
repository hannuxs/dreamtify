from django.contrib import admin

from .models import AuditLog, BankAccount, FaqItem, SiteSetting


def _superuser_only(request):
    """/kelola/sistem/ hanya untuk superuser (darurat), bukan operasional harian."""
    return request.user.is_active and request.user.is_superuser


admin.site.has_permission = _superuser_only


@admin.register(SiteSetting)
class SiteSettingAdmin(admin.ModelAdmin):
    list_display = ("brand_name", "admin_whatsapp", "email_notifications_enabled", "updated_at")

    def has_add_permission(self, request):
        return not SiteSetting.objects.exists()


@admin.register(BankAccount)
class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("bank_name", "account_number", "account_holder", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")


@admin.register(FaqItem)
class FaqItemAdmin(admin.ModelAdmin):
    list_display = ("question", "is_active", "sort_order")
    list_editable = ("is_active", "sort_order")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "actor_label", "action", "object_type", "object_id", "summary")
    list_filter = ("action",)
    search_fields = ("summary", "actor_label", "object_id")
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
