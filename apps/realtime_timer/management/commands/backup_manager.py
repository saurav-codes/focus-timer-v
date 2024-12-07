import logging
from django.core.management.base import BaseCommand
from django.core.management import call_command
from datetime import datetime

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Django management command to handle all backup-related operations:
    1. Creates a new backup
    2. Manages backup retention (removes old backups)
    3. Verifies backup integrity
    4. Pushes backups to GitHub
    
    Usage:
        python manage.py backup_manager
    """

    help = 'Manages all backup operations (create, verify, rotate, and push to GitHub)'

    def handle(self, *args, **options):
        try:
            timestamp = datetime.now().strftime('%B %d, %Y %I:%M %p')
            self.stdout.write(f"Starting backup operations at {timestamp}",style_func=self.style.WARNING)

            # Step 1: Create new backup
            self.stdout.write("Creating new backup...",style_func=self.style.WARNING)
            call_command('backup_database')

            # Step 2: Manage backups (includes verification)
            self.stdout.write("Managing and verifying backups...",style_func=self.style.WARNING)
            call_command('manage_backups')

            # Step 3: Push to GitHub
            self.stdout.write("Pushing backups to GitHub...",style_func=self.style.WARNING)
            call_command('backup_git_push')

            self.stdout.write(
                self.style.SUCCESS('All backup operations completed successfully')
            )

        except Exception as e:
            logger.error(f"Backup operations failed: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'Backup operations failed: {str(e)}')
            ) 