"""
Management command to import house data from the PHP project's SQL dump.

Usage:
    python manage.py import_houses
    python manage.py import_houses --sql-file path/to/db_housing.sql
    python manage.py import_houses --clear  (delete existing houses first)
"""
import os
import re

from django.core.management.base import BaseCommand, CommandError

from housing.models import House

DEFAULT_SQL_PATHS = [
    r'C:\Users\jumero1\AppData\Local\Temp\db_housing.sql',
    r'C:\Users\jumero1\Downloads\CAPSTONE_F1_DATABASE\CAPSTONE_F1_DATABASE\CAPSTONE_F1_SYSTEM\CAPSTONE_F1\db_housing.sql',
]

# Regex to match tbl_houses INSERT rows:
#   (id, site_id, 'Block No. X | Lot No. Y', 'household_head', 'Vacant|Occupied', 'M...svg...z')
ROW_RE = re.compile(
    r"\((\d+),\s*(\d+),\s*'(Block[^']+)',\s*'([^']*)',\s*'(Vacant|Occupied)',\s*'([^']*)'\)"
)


class Command(BaseCommand):
    help = 'Import 773 houses from the PHP project SQL dump (tbl_houses)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--sql-file',
            default=None,
            help='Path to the SQL dump file (auto-detected if omitted)',
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            default=False,
            help='Delete all existing House records before importing',
        )

    def handle(self, *args, **options):
        sql_file = options['sql_file']

        if sql_file is None:
            for path in DEFAULT_SQL_PATHS:
                if os.path.exists(path):
                    sql_file = path
                    break

        if not sql_file or not os.path.exists(sql_file):
            raise CommandError(
                'SQL file not found. Pass --sql-file <path> or place the file at:\n'
                + '\n'.join(f'  {p}' for p in DEFAULT_SQL_PATHS)
            )

        self.stdout.write(f'Reading SQL from: {sql_file}')

        with open(sql_file, 'r', encoding='utf-8', errors='replace') as fh:
            content = fh.read()

        rows = ROW_RE.findall(content)
        if not rows:
            raise CommandError('No tbl_houses rows found in the SQL file.')

        self.stdout.write(f'Found {len(rows)} house rows.')

        if options['clear']:
            deleted, _ = House.objects.all().delete()
            self.stdout.write(f'Deleted {deleted} existing house records.')

        houses = []
        for pk, site_id, house_address, _household_head, status, coordinates in rows:
            django_status = 'available' if status == 'Vacant' else 'occupied'
            houses.append(House(
                id=int(pk),
                site=int(site_id),
                house_number=house_address,
                svg_id=f'house-{pk}',
                status=django_status,
                coordinates=coordinates,
            ))

        House.objects.bulk_create(houses, ignore_conflicts=True)
        self.stdout.write(self.style.SUCCESS(
            f'Successfully imported {len(houses)} houses '
            f'({sum(1 for h in houses if h.site == 1)} in Site 1, '
            f'{sum(1 for h in houses if h.site == 2)} in Site 2).'
        ))
