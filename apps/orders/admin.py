"""
Django admin bawaan (darurat). NIK & rekening refund TIDAK pernah tampil utuh
di sini — hanya versi tersamar. Lihat NIK penuh lewat dashboard (Owner, diaudit).
"""
from django.contrib import admin

from .models import Order, OrderLine, OrderTimeline, Payment, TicketSlot, VaNotice

NIK_FIELDS = ("holder_nik", "holder_nik_hash")


class OrderLineInline(admin.StackedInline):
    model = OrderLine
    extra = 0
    exclude = NIK_FIELDS
    readonly_fields = ("nik_masked", "tier_snapshot", "fee_per_ticket_snapshot",
                       "price_basis_per_ticket_snapshot", "early_booking_per_ticket_snapshot")
    show_change_link = True

    @admin.display(description="NIK")
    def nik_masked(self, obj):
        return obj.nik_masked


class PaymentInline(admin.TabularInline):
    model = Payment
    extra = 0
    fields = ("kind", "status", "amount_claimed", "amount_received", "sender_name", "verified_at")
    readonly_fields = fields
    can_delete = False


class TimelineInline(admin.TabularInline):
    model = OrderTimeline
    extra = 0
    fields = ("created_at", "status", "title", "message", "is_public", "created_by_label")
    readonly_fields = fields
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("code", "buyer_name", "event", "phase", "status", "ticket_payment_method", "created_at")
    list_filter = ("status", "ticket_payment_method", "event")
    search_fields = ("code", "buyer_name", "buyer_whatsapp", "buyer_email")
    exclude = ("refund_account_number",)
    readonly_fields = ("code", "refund_account_masked", "pricing_snapshot", "fee_due", "pelunasan_due",
                       "unique_discount", "unique_code")
    list_select_related = ("event", "phase")
    inlines = [OrderLineInline, PaymentInline, TimelineInline]

    @admin.display(description="no. rekening refund")
    def refund_account_masked(self, obj):
        return obj.refund_account_masked


@admin.register(OrderLine)
class OrderLineAdmin(admin.ModelAdmin):
    list_display = ("order", "holder_name", "service_type", "quantity", "nik_masked")
    search_fields = ("order__code", "holder_name")
    exclude = NIK_FIELDS
    readonly_fields = ("nik_masked",)
    list_select_related = ("order",)

    @admin.display(description="NIK")
    def nik_masked(self, obj):
        return obj.nik_masked


@admin.register(TicketSlot)
class TicketSlotAdmin(admin.ModelAdmin):
    list_display = ("__str__", "result", "secured_category", "fulfillment_status")
    list_filter = ("result", "fulfillment_status")
    list_select_related = ("line__order", "secured_category")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "kind", "status", "amount_claimed", "amount_received", "created_at")
    list_filter = ("kind", "status")
    search_fields = ("order__code", "sender_name")
    list_select_related = ("order",)


@admin.register(VaNotice)
class VaNoticeAdmin(admin.ModelAdmin):
    list_display = ("order", "source", "bank", "amount", "status", "expires_at")
    list_filter = ("status", "source")


@admin.register(OrderTimeline)
class OrderTimelineAdmin(admin.ModelAdmin):
    list_display = ("order", "created_at", "title", "is_public")
    search_fields = ("order__code", "title")
