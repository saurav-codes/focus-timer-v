from django.urls import path
from . import views
from . import htmx_views
from .routing import websocket_urlpatterns
from django.conf import settings
from django.conf.urls.static import static


app_name = "realtime_timer"

urlpatterns = [
    path("", views.LandingPageView.as_view(), name="landing-page"),
    path("sessions-list/", views.SessionListView.as_view(), name="sessions-list-view"),
    path("session-form/", views.SessionFormView.as_view(), name="session-form-view"),
    path("session/<uuid:session_id>/", views.SessionDetailView.as_view(), name="session-detail-view"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard-view"),
    path("get-technique-info/", views.get_technique_info, name="get-technique-info"),
]

htmx_urlpatterns = [
    path("task/create/<uuid:session_id>/", htmx_views.create_task, name="create_task"),
    path("task/<int:task_id>/toggle/", htmx_views.toggle_task, name="toggle_task"),
    path(
        "temporary-focus-cycles-generator/",
        htmx_views.temporary_focus_cycles_generator_view,
        name="temporary-focus-cycles-generator-view",
    ),
    path(
        "focus-cycles-and-session-create/",
        htmx_views.focus_cycles_and_session_create_view,
        name="focus-cycles-and-session-create-view",
    ),
    path(
        "add-cycle-to-cycle-table/",
        htmx_views.add_cycle_to_cycle_table_view,
        name="add-cycle-to-cycle-table-view",
    ),
    path("delete-task/<int:task_id>/", htmx_views.delete_task, name="delete_task"),
]

urlpatterns += htmx_urlpatterns
urlpatterns += websocket_urlpatterns

# static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
