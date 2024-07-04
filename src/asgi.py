"""
ASGI config for src project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.0/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
import apps.realtime_timer.routing
from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler


os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.settings")
from django.conf import settings

django_asgi_app = get_asgi_application()
# Use ASGIStaticFilesHandler only in development
if settings.DEBUG:
    django_asgi_app = ASGIStaticFilesHandler(django_asgi_app)


application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(apps.realtime_timer.routing.websocket_urlpatterns)),
    }
)
