import time

from django.core.management.base import BaseCommand
from django.db import connections


class Command(BaseCommand):
    """Ожидает готовности базы данных (используется в entrypoint.sh)."""

    help = "Ожидает готовности базы данных."

    def handle(self, *args, **options):
        connection = connections["default"]
        for attempt in range(60):
            try:
                connection.ensure_connection()
                self.stdout.write(self.style.SUCCESS("Database is ready."))
                return
            except Exception:
                self.stdout.write(f"Waiting for database... ({attempt + 1}/60)")
                time.sleep(2)
        raise SystemExit("Database is not available after 120 seconds.")