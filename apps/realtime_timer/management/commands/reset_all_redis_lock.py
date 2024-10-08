from django.core.management.base import BaseCommand
import logging
from django.conf import settings
import redis
import redis_lock

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Reset all redis locks"

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Resetting all redis locks"))
        redis_client = redis.Redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}")
        redis_lock.reset_all(redis_client)
        self.stdout.write(self.style.SUCCESS("All redis locks reset"))
