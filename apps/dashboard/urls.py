from django.urls import path

from . import views, views_events, views_orders, views_owner, views_verify

app_name = "dashboard"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("", views.home, name="home"),
    path("menu/", views.menu, name="menu"),
    # Event
    path("event/", views_events.event_list, name="event_list"),
    path("event/baru/", views_events.event_create, name="event_create"),
    path("event/<int:pk>/", views_events.event_edit, name="event_edit_default"),
    path("event/<int:pk>/duplikat/", views_events.event_duplicate, name="event_duplicate"),
    path("event/<int:pk>/<slug:tab>/", views_events.event_edit, name="event_edit"),
    # Pesanan
    path("pesanan/", views_orders.order_list, name="order_list"),
    path("pesanan/<str:code>/", views_orders.order_detail, name="order_detail"),
    path("pesanan/<str:code>/aksi/<slug:action>/", views_orders.order_action, name="order_action"),
    path("pesanan/<str:code>/baris/<int:line_id>/", views_orders.line_update, name="line_update"),
    path("pesanan/<str:code>/pemegang/<int:line_id>/", views_orders.holder_edit, name="holder_edit"),
    path("pesanan/<str:code>/nik/<int:line_id>/", views_orders.reveal_nik, name="reveal_nik"),
    path("verifikasi/", views_verify.verify_queue, name="verify_queue"),
    path("verifikasi/<int:pk>/", views_verify.verify_action, name="verify_action"),
    path("waiting-list/", views_verify.waitlist, name="waitlist"),
    # Owner
    path("pengaturan/", views_owner.redirect_settings, name="settings"),
    path("pengaturan/<slug:tab>/", views_owner.settings_page, name="settings_tab"),
    path("pengguna/", views_owner.user_list, name="user_list"),
    path("pengguna/baru/", views_owner.user_create, name="user_create"),
    path("pengguna/<int:pk>/", views_owner.user_edit, name="user_edit"),
    path("pengguna/<int:pk>/sandi/", views_owner.user_password, name="user_password"),
    path("log/", views_owner.audit_log, name="audit_log"),
]
