from django.contrib import admin
from django.urls import include, path

from apps.core.views import health, public_media

admin.site.site_header = "Dreamtify — Sistem (darurat)"
admin.site.site_title = "Dreamtify Sistem"
admin.site.index_title = "Data mentah"

urlpatterns = [
    path("sehat/", health, name="health"),
    path("media/public/<path:path>", public_media, name="public_media"),
    # Django admin bawaan, hanya untuk superuser (keadaan darurat)
    path("kelola/sistem/", admin.site.urls),
    path("kelola/", include("apps.dashboard.urls")),
    path("", include("apps.public.urls")),
]
