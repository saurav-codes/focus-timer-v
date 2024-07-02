from django.urls import path
from . import views


urlpatterns = [
    path("", views.home, name="home"),
    path("start/", views.start_session, name="start_session"),
    path("active/", views.active_session, name="active_session"),
    path("end/", views.end_session, name="end_session"),
    path("join/<int:streamer_id>/", views.join_session, name="join_session"),
    path("analytics/", views.analytics, name="analytics"),
    path("toggle-theme/", views.toggle_theme, name="toggle_theme"),
    path("custom-technique/", views.custom_technique, name="custom_technique"),
    path("update-session/", views.update_session, name="update_session"),
]
