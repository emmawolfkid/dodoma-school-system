import os
import subprocess
from datetime import datetime

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Dumps the Postgres database to backups/ using pg_dump (custom "
        "format, restorable with pg_restore). Keeps the most recent N "
        "backups and deletes older ones."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--keep', type=int, default=14,
            help="Number of most recent backups to keep (default: 14).",
        )
        parser.add_argument(
            '--output-dir', default=None,
            help="Where to write backups (default: BASE_DIR/backups).",
        )

    def handle(self, *args, **options):
        db = settings.DATABASES['default']
        if 'postgresql' not in db['ENGINE']:
            raise CommandError("backup_database only supports the postgresql engine.")

        backup_dir = options['output_dir'] or (settings.BASE_DIR / 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_name = db['NAME']
        filename = os.path.join(backup_dir, f"{db_name}_{timestamp}.dump")

        env = os.environ.copy()
        if db.get('PASSWORD'):
            env['PGPASSWORD'] = db['PASSWORD']

        cmd = [
            'pg_dump',
            '-Fc',  # custom format: compressed, restorable with pg_restore, supports selective restore
            '-h', db.get('HOST') or 'localhost',
            '-p', str(db.get('PORT') or '5432'),
            '-U', db.get('USER') or 'postgres',
            '-f', filename,
            db_name,
        ]

        self.stdout.write(f"Backing up '{db_name}' to {filename} ...")
        try:
            result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        except FileNotFoundError:
            raise CommandError(
                "pg_dump was not found on PATH. Install the PostgreSQL client "
                "tools (the same version as your server) and make sure "
                "pg_dump is on PATH, then try again."
            )

        if result.returncode != 0:
            if os.path.exists(filename):
                os.remove(filename)  # don't leave a partial/corrupt dump behind
            raise CommandError(f"pg_dump failed:\n{result.stderr}")

        size_mb = os.path.getsize(filename) / (1024 * 1024)
        self.stdout.write(self.style.SUCCESS(f"Backup complete: {filename} ({size_mb:.1f} MB)"))

        self._prune_old_backups(backup_dir, db_name, options['keep'])

    def _prune_old_backups(self, backup_dir, db_name, keep):
        backups = sorted(
            (f for f in os.listdir(backup_dir) if f.startswith(db_name) and f.endswith('.dump')),
            reverse=True,
        )
        for old in backups[keep:]:
            os.remove(os.path.join(backup_dir, old))
            self.stdout.write(f"Removed old backup: {old}")
