from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Creates initial focus techniques"

    def handle(self, *args, **kwargs):
        ...
