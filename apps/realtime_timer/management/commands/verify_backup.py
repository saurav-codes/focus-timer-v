import os
import sqlite3
import tempfile
from django.core.management.base import BaseCommand
from django.conf import settings
from django.apps import apps
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    """
    Django management command to verify the integrity of SQLite database backups.
    This command:
    1. Creates a temporary database
    2. Restores the backup to this temporary database
    3. Verifies:
       - Table structures match the original
       - Row counts match
       - Foreign key constraints are valid
    
    Usage:
        python manage.py verify_backup  # verifies latest backup
        python manage.py verify_backup --backup-file=/path/to/backup.db  # verifies specific backup
    """

    help = 'Verifies SQLite backup integrity and tests restoration'

    def add_arguments(self, parser):
        # Allow specifying a particular backup file to verify
        parser.add_argument(
            '--backup-file',
            help='Specific backup file to verify. If not provided, verifies latest backup.'
        )

    def verify_table_structure(self, source_conn, test_conn, table_name):
        """
        Compare table schemas between original and restored databases.
        Uses SQLite's sqlite_master table to get the CREATE TABLE statements
        and compares them.
        """
        source_schema = source_conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
        test_schema = test_conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,)).fetchone()
        return source_schema == test_schema

    def verify_row_counts(self, source_conn, test_conn, table_name):
        """
        Compare the number of rows in each table between original and restored databases.
        A simple COUNT(*) should match if the backup is valid.
        """
        source_count = source_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        test_count = test_conn.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        return source_count == test_count

    def verify_foreign_keys(self, conn):
        """
        Verify that all foreign key constraints are valid in the restored database.
        Uses SQLite's PRAGMA foreign_key_check which returns empty list if all constraints are valid.
        """
        return conn.execute("PRAGMA foreign_key_check").fetchall() == []

    def handle(self, *args, **options):
        try:
            backup_dir = settings.SQLITE_BACKUP['BACKUP_DIRECTORY']
            
            # Determine which backup file to verify
            if options['backup_file']:
                backup_path = Path(options['backup_file'])
                if not backup_path.exists():
                    raise FileNotFoundError(f"Backup file not found: {backup_path}")
            else:
                # If no specific file provided, get the most recent backup
                backup_files = sorted(
                    Path(backup_dir).glob('backup_*.db'),
                    key=lambda x: x.stat().st_mtime,
                    reverse=True
                )
                if not backup_files:
                    raise FileNotFoundError("No backup files found")
                backup_path = backup_files[0]

            # Create a temporary database file for testing restoration
            with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as temp_db:
                temp_db_path = temp_db.name

            try:
                # Connect to both backup and temporary database
                backup_conn = sqlite3.connect(str(backup_path))
                test_conn = sqlite3.connect(temp_db_path)
                
                # Restore the backup to temporary database
                with backup_conn, test_conn:
                    backup_conn.backup(test_conn)

                # Get all table names from Django models
                django_tables = [
                    model._meta.db_table
                    for model in apps.get_models()
                ]

                # Store verification results
                verification_results = {
                    'structure': [],  # Table structure verification results
                    'row_counts': [], # Row count verification results
                    'foreign_keys': True  # Foreign key constraint verification
                }

                # Verify each table
                for table in django_tables:
                    # Check if table structures match
                    structure_match = self.verify_table_structure(backup_conn, test_conn, table)
                    verification_results['structure'].append({
                        'table': table,
                        'matches': structure_match
                    })

                    # Check if row counts match
                    count_match = self.verify_row_counts(backup_conn, test_conn, table)
                    verification_results['row_counts'].append({
                        'table': table,
                        'matches': count_match
                    })

                # Verify foreign key constraints
                verification_results['foreign_keys'] = self.verify_foreign_keys(test_conn)

                # Check if all verifications passed
                all_passed = (
                    all(r['matches'] for r in verification_results['structure']) and
                    all(r['matches'] for r in verification_results['row_counts']) and
                    verification_results['foreign_keys']
                )

                if all_passed:
                    # All checks passed - backup is valid
                    logger.info(f"Backup verification successful for {backup_path}")
                    self.stdout.write(
                        self.style.SUCCESS(f'Backup verification successful for {backup_path}')
                    )
                else:
                    # Collect all failed checks for detailed error reporting
                    failed_checks = []
                    for result in verification_results['structure']:
                        if not result['matches']:
                            failed_checks.append(f"Structure mismatch in table {result['table']}")
                    
                    for result in verification_results['row_counts']:
                        if not result['matches']:
                            failed_checks.append(f"Row count mismatch in table {result['table']}")
                    
                    if not verification_results['foreign_keys']:
                        failed_checks.append("Foreign key constraints validation failed")

                    logger.error(f"Backup verification failed for {backup_path}: {', '.join(failed_checks)}")
                    self.stdout.write(
                        self.style.ERROR(f'Backup verification failed: {", ".join(failed_checks)}')
                    )

            finally:
                # Clean up: remove temporary database
                if os.path.exists(temp_db_path):
                    os.unlink(temp_db_path)

        except Exception as e:
            logger.error(f"Backup verification failed: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f'Backup verification failed: {str(e)}')
            ) 