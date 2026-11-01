from django.urls import path

from . import lacak_views, order_views, promotor_views, views

app_name = "public"

urlpatterns = [
    path("", views.home, name="home"),
    path("testimoni/", views.testimonials, name="testimonials"),
    path("faq/", views.faq, name="faq"),
    path("syarat/", views.terms, name="terms"),
    path("privasi/", views.privacy, name="privacy"),
    path("robots.txt", views.robots, name="robots"),
    path("sitemap.xml", views.sitemap, name="sitemap"),
    path("event/<slug:slug>/", order_views.event_detail, name="event_detail"),
    path("event/<slug:slug>/pesan/", order_views.order_form, name="order_form"),
    path("event/<slug:slug>/pesan/hitung/", order_views.order_quote, name="order_quote"),
    path("pesanan/<str:code>/berhasil/", order_views.order_success, name="order_success"),
    path("lacak/", lacak_views.track_login, name="track_login"),
    path("lacak/<str:code>/", lacak_views.track_order, name="track_order"),
    path("lacak/<str:code>/bayar/", lacak_views.track_pay, name="track_pay"),
    path("lacak/<str:code>/rekening/", lacak_views.track_refund_account, name="track_refund_account"),
    path("lacak/<str:code>/batal/", lacak_views.track_cancel, name="track_cancel"),
    path("lacak/<str:code>/pemegang/<int:line_id>/", lacak_views.track_holder_edit, name="track_holder_edit"),
    path("lacak/<str:code>/testimoni/", lacak_views.track_testimonial, name="track_testimonial"),
    path("lacak/<str:code>/va/<int:va_id>/klaim/", lacak_views.track_va_claim, name="track_va_claim"),
    path("lacak/<str:code>/va-mandiri/", lacak_views.track_va_mandiri, name="track_va_mandiri"),
    path("berkas/<slug:kind>/<int:pk>/", lacak_views.private_file, name="private_file"),
    path("p/<str:token>/", promotor_views.promotor_page, name="promotor"),
    path("p/<str:token>/unduh.<slug:fmt>", promotor_views.promotor_download, name="promotor_download"),
    path("p/<str:token>/bukti/<int:payment_id>/", promotor_views.promotor_proof, name="promotor_proof"),
    # Hanya aktif saat DEBUG (view mengembalikan 404 di produksi)
    path("_komponen/", views.component_gallery, name="component_gallery"),
    path("_komponen/dashboard/", views.dashboard_preview, name="dashboard_preview"),
    path("_komponen/<int:code>/", views.error_preview, name="error_preview"),
]
