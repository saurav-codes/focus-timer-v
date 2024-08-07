import os
from django.core.asgi import get_asgi_application

# Set the Django settings module
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "src.settings")

# Initialize Django ASGI application early to ensure the AppRegistry is populated
# before importing any models or other parts of the framework that rely on it.
django_asgi_app = get_asgi_application()

# Import other necessary modules after initializing Django
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from django.conf import settings

# Use ASGIStaticFilesHandler only in development
if settings.DEBUG:
    from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler

    django_asgi_app = ASGIStaticFilesHandler(django_asgi_app)

# Import your application's routing configuration
import apps.realtime_timer.routing

# Define the application
application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(URLRouter(apps.realtime_timer.routing.websocket_urlpatterns)),
    }
)
