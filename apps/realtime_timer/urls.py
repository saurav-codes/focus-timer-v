from django.urls import path
from . import views
from . import htmx_views
from .routing import websocket_urlpatterns
from django.conf import settings
from django.conf.urls.static import static


app_name = "realtime_timer"

urlpatterns = [
    path("", views.LandingPageView.as_view(), name="landing-page"),
    path("home/", views.HomepageView.as_view(), name="homepage-view"),
    path("main-session/", views.MainSessionView.as_view(), name="main-session-view"),
    path("session/<uuid:session_id>/", views.SessionDetailView.as_view(), name="session-detail-view"),
    # path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    # path("task/create/", views.CreateTaskView.as_view(), name="create_task"),
    # path("task/<int:task_id>/toggle/", views.ToggleTaskView.as_view(), name="toggle_task"),
]

htmx_urlpatterns = [
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
]

urlpatterns += htmx_urlpatterns
urlpatterns += websocket_urlpatterns

# static files in development
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
