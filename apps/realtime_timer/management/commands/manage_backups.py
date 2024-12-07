import os
import glob
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.conf import settings
import logging
from django.core.management import call_command

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Django management command to manage SQLite database backups.
    This command:
    1. Removes old backups exceeding the maximum count
    2. Verifies the integrity of remaining backups
    
    Usage:
        python manage.py manage_backups

    Configuration is read from settings.SQLITE_BACKUP:
        BACKUP_DIRECTORY: Where backups are stored
        BACKUP_MAX_COUNT: Maximum number of backups to keep
    """

    help = 'Manages SQLite database backups by removing old ones'

    def handle(self, *args, **options):
        try:
            # Get backup settings from Django settings
            backup_dir = settings.SQLITE_BACKUP['BACKUP_DIRECTORY']
            max_backups = settings.SQLITE_BACKUP['BACKUP_MAX_COUNT']

            # Get all backup files and sort them by modification time
            # newest files first
            backup_files = glob.glob(os.path.join(backup_dir, 'backup_*.db'))
            backup_files.sort(key=os.path.getmtime, reverse=True)

            # If we have more backups than the maximum allowed
            if len(backup_files) > max_backups:
                # Remove the oldest backups (those beyond max_backups)
                for old_backup in backup_files[max_backups:]:
                    os.remove(old_backup)
                    logger.info(f"Removed old backup: {old_backup}")
                    self.stdout.write(
                        self.style.SUCCESS(f'Removed old backup: {old_backup}')
                    )

            # After cleanup, verify all remaining backups
            # This calls the verify_backup command for each backup file
            for backup_file in backup_files[:max_backups]:
                self.stdout.write(f"Verifying backup: {backup_file}")
                call_command('verify_backup', backup_file=str(backup_file))

        except Exception as e:
            logger.error(f"Backup management failed: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'Backup management failed: {str(e)}')
            ) 