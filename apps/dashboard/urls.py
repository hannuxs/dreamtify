from django.urls import path

from . import views, views_events, views_owner

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
    # Owner
    path("pengaturan/", views_owner.redirect_settings, name="settings"),
    path("pengaturan/<slug:tab>/", views_owner.settings_page, name="settings_tab"),
    path("pengguna/", views_owner.user_list, name="user_list"),
    path("pengguna/baru/", views_owner.user_create, name="user_create"),
    path("pengguna/<int:pk>/", views_owner.user_edit, name="user_edit"),
    path("pengguna/<int:pk>/sandi/", views_owner.user_password, name="user_password"),
    path("log/", views_owner.audit_log, name="audit_log"),
]
