import os
import sqlite3
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Django management command to create SQLite database backups.
    Uses SQLite's built-in online backup API which allows creating backups
    while the database is in use.

    Usage:
        python manage.py backup_database

    The backup will be stored in the BACKUP_DIRECTORY specified in settings.SQLITE_BACKUP
    with a timestamp in the filename.
    """

    help = 'Creates a backup of the SQLite database using the online backup API'

    def handle(self, *args, **options):
        try:
            # Create backup directory if it doesn't exist
            # Uses the path specified in settings.SQLITE_BACKUP['BACKUP_DIRECTORY']
            backup_dir = os.path.join(settings.BASE_DIR, 'backups')
            os.makedirs(backup_dir, exist_ok=True)

            # Create a timestamp for unique backup filename
            # Format: YYYYMMDD_HHMMSS
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Get the path of the current database from Django settings
            db_path = settings.DATABASES['default']['NAME']
            
            # Generate the backup filepath with timestamp
            backup_path = os.path.join(backup_dir, f'backup_{timestamp}.db')

            # Open connection to the source (current) database
            source = sqlite3.connect(db_path)
            
            # Create a new connection for the backup database
            backup = sqlite3.connect(backup_path)

            # Use SQLite's backup API to create the backup
            # The backup() method is atomic and will maintain consistency
            # even if the database is being written to during backup
            with source, backup:
                source.backup(backup)
                logger.info(f"Database backup created successfully at {backup_path}")
                self.stdout.write(
                    self.style.SUCCESS(f'Successfully created backup at {backup_path}')
                )

        except Exception as e:
            logger.error(f"Database backup failed: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'Backup failed: {str(e)}')
            ) 