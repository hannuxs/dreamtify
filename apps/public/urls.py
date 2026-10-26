from django.urls import path

from . import order_views, views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("event/<slug:slug>/", order_views.event_detail, name="event_detail"),
    path("event/<slug:slug>/pesan/", order_views.order_form, name="order_form"),
    path("event/<slug:slug>/pesan/hitung/", order_views.order_quote, name="order_quote"),
    path("pesanan/<str:code>/berhasil/", order_views.order_success, name="order_success"),
    # Hanya aktif saat DEBUG (view mengembalikan 404 di produksi)
    path("_komponen/", views.component_gallery, name="component_gallery"),
    path("_komponen/dashboard/", views.dashboard_preview, name="dashboard_preview"),
    path("_komponen/<int:code>/", views.error_preview, name="error_preview"),
]
