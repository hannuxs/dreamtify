from django.contrib import admin

from .models import Event, FeeRule, SalePhase, TicketCategory


class SalePhaseInline(admin.TabularInline):
    model = SalePhase
    extra = 0
    fields = ("name", "sort_order", "status", "order_open_at", "order_close_at", "war_at",
              "pelunasan_deadline", "slot_quota", "membership_required")


class TicketCategoryInline(admin.TabularInline):
    model = TicketCategory
    extra = 0
    fields = ("name", "fee_tier", "price", "sort_order", "is_active")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("name", "status", "first_show_date", "city")
    list_filter = ("status",)
    search_fields = ("name", "artist")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [SalePhaseInline, TicketCategoryInline]
    readonly_fields = ("promotor_token",)


class FeeRuleInline(admin.TabularInline):
    model = FeeRule
    extra = 0


@admin.register(SalePhase)
class SalePhaseAdmin(admin.ModelAdmin):
    list_display = ("__str__", "status", "war_at", "slot_quota")
    list_filter = ("status",)
    inlines = [FeeRuleInline]


@admin.register(TicketCategory)
class TicketCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "event", "fee_tier", "price", "is_active")
    list_filter = ("event",)


@admin.register(FeeRule)
class FeeRuleAdmin(admin.ModelAdmin):
    list_display = ("phase", "service_type", "fee_tier", "fee_per_ticket")
    list_filter = ("phase__event",)
