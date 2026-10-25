from django.contrib import admin
from django.urls import include, path

from apps.core.views import health

admin.site.site_header = "Dreamtify — Sistem (darurat)"
admin.site.site_title = "Dreamtify Sistem"
admin.site.index_title = "Data mentah"

urlpatterns = [
    path("sehat/", health, name="health"),
    # Django admin bawaan, hanya untuk superuser (keadaan darurat)
    path("kelola/sistem/", admin.site.urls),
    path("", include("apps.public.urls")),
]
