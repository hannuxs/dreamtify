from django.urls import path

from . import views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    # Hanya aktif saat DEBUG (view mengembalikan 404 di produksi)
    path("_komponen/", views.component_gallery, name="component_gallery"),
    path("_komponen/dashboard/", views.dashboard_preview, name="dashboard_preview"),
    path("_komponen/<int:code>/", views.error_preview, name="error_preview"),
]
