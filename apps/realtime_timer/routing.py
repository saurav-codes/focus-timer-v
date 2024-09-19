from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/focus_session/(?P<session_id>[^/]+)/(?P<username>[^/]+)$", consumers.FocusSessionConsumer.as_asgi()),
]
