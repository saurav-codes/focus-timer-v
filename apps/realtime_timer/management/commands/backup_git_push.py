import os
import subprocess
from datetime import datetime
from django.core.management.base import BaseCommand
from django.conf import settings
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Django management command to commit and push database backups to GitHub.
    This command:
    1. Stages all new backup files
    2. Creates a commit with timestamp
    3. Pushes to the configured remote branch
    
    Usage:
        python manage.py backup_git_push

    Required Environment Variables:
        GIT_USER_NAME: Git user name for commits
        GIT_USER_EMAIL: Git user email for commits
        GIT_BRANCH: Branch to push backups (default: backup)
    """

    help = 'Commits and pushes database backups to GitHub'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt and force push backup',
        )

    def execute_git_command(self, command, error_message):
        """Execute git command and handle errors"""
        try:
            result = subprocess.run(
                command,
                cwd=settings.BASE_DIR,
                check=True,
                capture_output=True,
                text=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"{error_message}: {e.stderr}")
            raise

    def handle(self, *args, **options):
        try:
            backup_dir = settings.SQLITE_BACKUP['BACKUP_DIRECTORY']
            git_user = settings.GIT_USER_NAME
            git_email = settings.GIT_USER_EMAIL

            if not all([git_user, git_email]):
                raise ValueError("GIT_USER_NAME and GIT_USER_EMAIL must be set in environment")

            # Configure git user for this commit
            self.execute_git_command(
                ['git', 'config', 'user.name', git_user],
                "Failed to set git user name"
            )
            self.execute_git_command(
                ['git', 'config', 'user.email', git_email],
                "Failed to set git user email"
            )

            # Add confirmation prompt unless --force flag is used
            if not options['force']:
                confirm = input(
                    "\nWARNING: You are about to push database backups to a remote repository.\n"
                    "This may override existing data in the repository.\n"
                    "Are you sure you want to continue? [y/N]: "
                ).lower()
                if confirm not in ['y', 'yes']:
                    self.stdout.write(self.style.WARNING('Backup push cancelled'))
                    return

            # Stage all backup files
            backup_pattern = os.path.join(backup_dir, 'backup_*.db')
            self.execute_git_command(
                ['git', 'add', backup_pattern],
                "Failed to stage backup files"
            )

            # Create commit with timestamp
            # this time is in UTC+0 
            timestamp = datetime.now().strftime('%B %d, %Y %I:%M %p')
            commit_message = f"Database backup - {timestamp}"
            self.execute_git_command(
                ['git', 'commit', '-m', commit_message],
                "Failed to create commit"
            )

            # Push to remote
            self.execute_git_command(
                ['git', 'push', 'origin'],
                "Failed to push to GitHub"
            )

            logger.info("Successfully pushed backup to GitHub")
            self.stdout.write(
                self.style.SUCCESS('Successfully pushed backup to GitHub')
            )

        except Exception as e:
            logger.error(f"Failed to push backup to GitHub: {str(e)}")
            self.stdout.write(
                self.style.ERROR('Failed to push backup to GitHub')
            ) 