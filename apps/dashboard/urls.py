from django.urls import path

from . import views, views_events, views_inbox, views_orders, views_owner, views_settlement, views_verify, views_war

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
    path("pesanan/<str:code>/kabar/", views_inbox.order_message, name="order_message"),
    # Mode War
    path("war/", views_war.war_index, name="war_index"),
    path("war/<int:phase_id>/", views_war.war_mode, name="war_mode"),
    path("war/<int:phase_id>/mulai/", views_war.war_start, name="war_start"),
    path("war/<int:phase_id>/selesai/", views_war.war_finish, name="war_finish"),
    path("war/tiket/<int:slot_id>/", views_war.war_slot, name="war_slot"),
    path("war/pesanan/<str:code>/va/", views_war.war_va, name="war_va"),
    path("war/va/<int:va_id>/lunas/", views_war.war_va_paid, name="war_va_paid"),
    # Penyelesaian & penyerahan
    path("penyelesaian/", views_settlement.settlement_page, name="settlement"),
    path("penyelesaian/refund/<str:code>/", views_settlement.refund_record, name="refund_record"),
    path("penyelesaian/ingatkan/<str:code>/<slug:kind>/", views_settlement.remind, name="remind"),
    path("penyelesaian/refund.xlsx", views_settlement.refund_export, name="refund_export"),
    path("penyerahan/", views_settlement.handover_page, name="handover"),
    path("penyerahan/aksi/", views_settlement.handover_action, name="handover_action"),
    path("penyerahan/gelang.xlsx", views_settlement.handover_export, name="handover_export"),
    # Kotak Kabar
    path("kabar/", views_inbox.inbox, name="inbox"),
    path("kabar/beruntun/", views_inbox.inbox_sequence, name="inbox_sequence"),
    path("kabar/<int:pk>/kirim/", views_inbox.inbox_send, name="inbox_send"),
    path("kabar/<int:pk>/lewati/", views_inbox.inbox_skip, name="inbox_skip"),
    path("kabar/<int:pk>/ubah/", views_inbox.inbox_edit, name="inbox_edit"),
    # Owner
    path("pengaturan/", views_owner.redirect_settings, name="settings"),
    path("pengaturan/template/<slug:key>/", views_inbox.template_edit, name="template_edit"),
    path("pengaturan/<slug:tab>/", views_owner.settings_page, name="settings_tab"),
    path("pengguna/", views_owner.user_list, name="user_list"),
    path("pengguna/baru/", views_owner.user_create, name="user_create"),
    path("pengguna/<int:pk>/", views_owner.user_edit, name="user_edit"),
    path("pengguna/<int:pk>/sandi/", views_owner.user_password, name="user_password"),
    path("log/", views_owner.audit_log, name="audit_log"),
]
