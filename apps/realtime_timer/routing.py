from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    # re_path(r"ws/timer/(?P<session_id>\w+)/$", consumers.TimerConsumer.as_asgi()),
]
