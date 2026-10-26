from django.contrib import admin

from .models import Testimonial


@admin.register(Testimonial)
class TestimonialAdmin(admin.ModelAdmin):
    list_display = ("display_name", "rating", "event", "status", "is_featured", "source", "created_at")
    list_filter = ("status", "source", "is_featured")
    search_fields = ("display_name", "text")
