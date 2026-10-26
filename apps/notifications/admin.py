from django.contrib import admin

from .models import MessageTemplate, Notification


@admin.register(MessageTemplate)
class MessageTemplateAdmin(admin.ModelAdmin):
    list_display = ("key", "title", "is_active", "send_email", "is_customized")
    search_fields = ("key", "title", "body")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("order", "template_key", "channel", "status", "created_at", "sent_at")
    list_filter = ("status", "channel", "template_key")
    search_fields = ("order__code", "recipient")
    list_select_related = ("order",)
