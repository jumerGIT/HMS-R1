"""
Management command to import all PHP project data into Django:
  - Users  (tbl_user + tbl_staff / tbl_client for profile info)
  - Applications  (tbl_profile + tbl_hhead)
  - House allocations  (tbl_profile.receiving_add → House.allocated_to)

Default passwords are set to the lowercase username so users can log in
immediately (e.g. username "Admin" → password "admin").

Usage:
    python manage.py import_data
    python manage.py import_data --sql-file path/to/db_housing.sql
    python manage.py import_data --clear     # wipe users/apps before import
"""
import re
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from housing.models import Application, CustomUser, House

DEFAULT_SQL_PATHS = [
    r'C:\Users\jumero1\AppData\Local\Temp\db_housing.sql',
    r'C:\Users\jumero1\Downloads\CAPSTONE_F1_DATABASE\CAPSTONE_F1_DATABASE'
    r'\CAPSTONE_F1_SYSTEM\CAPSTONE_F1\db_housing.sql',
]

# ---------------------------------------------------------------------------
# Low-level SQL parsing helpers
# ---------------------------------------------------------------------------

def _rows(sql, table):
    """
    Yield each row tuple (as a list of strings) from every INSERT INTO
    block for `table`.  Handles multi-row INSERT statements.
    Quoted strings are extracted correctly; integer/date values are kept
    as plain strings.
    """
    # Grab every INSERT block for this table (there may be several)
    block_re = re.compile(
        rf"INSERT INTO `{re.escape(table)}`\s*\([^)]+\)\s*VALUES\s*(.*?);",
        re.DOTALL,
    )
    for block in block_re.finditer(sql):
        values_text = block.group(1)
        # Walk through each row: (val, val, ...)
        row_re = re.compile(r'\(([^()]+)\)', re.DOTALL)
        for row_match in row_re.finditer(values_text):
            raw = row_match.group(1)
            # Split carefully: commas inside single-quoted strings are safe
            # because we parse token by token
            tokens = _split_row(raw)
            yield tokens


def _split_row(raw):
    """Split a VALUES row like  1, 'foo', 'bar, baz', 0  into tokens."""
    tokens = []
    current = ''
    in_quote = False
    i = 0
    while i < len(raw):
        ch = raw[i]
        if ch == "'" and not in_quote:
            in_quote = True
            i += 1
            continue
        if ch == "'" and in_quote:
            # escaped quote '' → single quote in value
            if i + 1 < len(raw) and raw[i + 1] == "'":
                current += "'"
                i += 2
                continue
            in_quote = False
            i += 1
            continue
        if ch == ',' and not in_quote:
            tokens.append(current.strip())
            current = ''
            i += 1
            continue
        current += ch
        i += 1
    if current.strip():
        tokens.append(current.strip())
    return tokens


# ---------------------------------------------------------------------------
# Table-specific parsers  →  list of dicts
# ---------------------------------------------------------------------------

def parse_tbl_user(sql):
    # uname, password, profile_id, role
    out = {}
    for uname, password, profile_id, role in _rows(sql, 'tbl_user'):
        out[profile_id] = {
            'uname': uname,
            'password_hash': password,
            'profile_id': profile_id,
            'role': role,
        }
    return out  # keyed by profile_id


def parse_tbl_staff(sql):
    # profile_id, fname, mname, lname, email, role
    out = {}
    for cols in _rows(sql, 'tbl_staff'):
        if len(cols) < 6:
            continue
        profile_id, fname, mname, lname, email, role = cols[:6]
        out[profile_id] = {
            'fname': fname, 'mname': mname, 'lname': lname,
            'email': email, 'role': role,
        }
    return out


def parse_tbl_client(sql):
    # profile_id, fname, lname, email
    out = {}
    for cols in _rows(sql, 'tbl_client'):
        if len(cols) < 4:
            continue
        profile_id, fname, lname, email = cols[:4]
        out[profile_id] = {
            'fname': fname, 'lname': lname, 'email': email,
        }
    return out


def parse_tbl_hhead(sql):
    # id, ref_id, fname, mname, lname, bdate, civil_stat, income, img
    out = {}
    for cols in _rows(sql, 'tbl_hhead'):
        if len(cols) < 5:
            continue
        _id, ref_id, fname, mname, lname = cols[:5]
        bdate = cols[5] if len(cols) > 5 else ''
        civil_stat = cols[6] if len(cols) > 6 else ''
        income_raw = cols[7] if len(cols) > 7 else '0'
        out[ref_id] = {
            'fname': fname, 'mname': mname, 'lname': lname,
            'bdate': bdate, 'civil_stat': civil_stat,
            'income': income_raw,
        }
    return out


def parse_tbl_profile(sql):
    # ref_id, household_type, head_bdate, spouse_bdate, tenurial_stat,
    # extent_damage, household_size, monthly_income, place_origin,
    # housing_option, contact_no, place_of_origin, sending_area, receiving_add
    out = {}
    for cols in _rows(sql, 'tbl_profile'):
        if len(cols) < 14:
            continue
        out[cols[0]] = {
            'ref_id':         cols[0],
            'household_type': cols[1],
            'head_bdate':     cols[2],
            'tenurial_stat':  cols[4],
            'extent_damage':  cols[5],
            'household_size': cols[6],
            'monthly_income': cols[7],
            'place_origin':   cols[8],
            'housing_option': cols[9],
            'contact_no':     cols[10],
            'sending_area':   cols[12],
            'receiving_add':  cols[13],
        }
    return out


# ---------------------------------------------------------------------------
# Role mapping
# ---------------------------------------------------------------------------

ROLE_MAP = {
    'Housing_incharge':    'housing_incharge',
    'Beneficiary_incharge': 'beneficiary_incharge',
    'Client/Applicant':    'applicant',
    'Administrator':       'admin',
}


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = 'Import users, applications and house allocations from the PHP SQL dump'

    def add_arguments(self, parser):
        parser.add_argument('--sql-file', default=None)
        parser.add_argument('--clear', action='store_true', default=False,
                            help='Delete non-superuser CustomUsers and all Applications first')

    def handle(self, *args, **options):
        # ── locate SQL file ──────────────────────────────────────────────
        sql_file = options['sql_file']
        if sql_file is None:
            import os
            for p in DEFAULT_SQL_PATHS:
                if os.path.exists(p):
                    sql_file = p
                    break
        if not sql_file:
            raise CommandError(
                'SQL file not found. Pass --sql-file <path>.'
            )
        self.stdout.write(f'Reading: {sql_file}')
        with open(sql_file, 'r', encoding='utf-8', errors='replace') as fh:
            sql = fh.read()

        # ── parse all relevant tables ────────────────────────────────────
        users_sql   = parse_tbl_user(sql)     # keyed by profile_id
        staff_sql   = parse_tbl_staff(sql)    # keyed by profile_id
        clients_sql = parse_tbl_client(sql)   # keyed by profile_id
        hheads_sql  = parse_tbl_hhead(sql)    # keyed by ref_id
        profiles_sql = parse_tbl_profile(sql) # keyed by ref_id

        self.stdout.write(
            f'  tbl_user={len(users_sql)}  tbl_staff={len(staff_sql)}  '
            f'tbl_client={len(clients_sql)}  tbl_profile={len(profiles_sql)}  '
            f'tbl_hhead={len(hheads_sql)}'
        )

        # ── optional clear ───────────────────────────────────────────────
        if options['clear']:
            deleted_apps, _ = Application.objects.all().delete()
            deleted_users = CustomUser.objects.filter(is_superuser=False).delete()[0]
            self.stdout.write(
                f'Cleared {deleted_users} users and {deleted_apps} applications.'
            )

        # ── 1. Create / update user accounts ────────────────────────────
        created_users = 0
        skipped_users = 0

        # Build a profile_id → username lookup from users_sql
        pid_to_uname = {v['profile_id']: v['uname'] for v in users_sql.values()}

        for profile_id, user_row in users_sql.items():
            uname    = user_row['uname']
            php_role = user_row['role']
            django_role = ROLE_MAP.get(php_role, 'applicant')

            # Get name + email from the appropriate profile table
            if django_role in ('housing_incharge', 'beneficiary_incharge', 'admin'):
                profile = staff_sql.get(profile_id, {})
            else:
                profile = clients_sql.get(profile_id, {})

            first_name = profile.get('fname', '')
            last_name  = profile.get('lname', '')
            email      = profile.get('email', '')

            if CustomUser.objects.filter(username__iexact=uname).exists():
                skipped_users += 1
                continue

            user = CustomUser(
                username   = uname,
                first_name = first_name,
                last_name  = last_name,
                email      = email,
                role       = django_role,
                is_active  = True,
            )
            # Set password = lowercase username (easy default for dev)
            user.set_password(uname.lower())
            user.save()
            created_users += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Users: created={created_users}, skipped={skipped_users}'
            )
        )

        # ── 2. Create Applications for tbl_profile entries ───────────────
        created_apps = 0
        skipped_apps = 0
        ref_to_applicant = {}   # ref_id -> CustomUser, used in step 3

        for ref_id, prof in profiles_sql.items():
            hhead  = hheads_sql.get(ref_id, {})
            client = clients_sql.get(ref_id, {})

            if hhead:
                first_name = hhead.get('fname', '')
                last_name  = hhead.get('lname', '')
                full_name  = f"{last_name}, {first_name} {hhead.get('mname', '')}".strip(', ')
            else:
                first_name = client.get('fname', '')
                last_name  = client.get('lname', '')
                full_name  = f"{first_name} {last_name}".strip()

            # ── resolve or create the Django user ──
            uname = pid_to_uname.get(ref_id)
            if uname:
                try:
                    applicant = CustomUser.objects.get(username__iexact=uname)
                except CustomUser.DoesNotExist:
                    skipped_apps += 1
                    continue
            else:
                # No tbl_user entry — create an applicant account from household head data
                raw_uname = (
                    f"{last_name.split(',')[0].strip()}_{first_name.split()[0].strip()}"
                    .lower().replace(' ', '_').replace('.', '')[:28]
                ) or f"app_{ref_id[:8]}"
                base, counter = raw_uname, 1
                while CustomUser.objects.filter(username=raw_uname).exists():
                    raw_uname = f"{base}{counter}"
                    counter += 1
                applicant = CustomUser(
                    username=raw_uname, first_name=first_name, last_name=last_name,
                    email=client.get('email', ''), role='applicant', is_active=True,
                )
                applicant.set_password(raw_uname)
                applicant.save()
                created_users += 1

            ref_to_applicant[ref_id] = applicant

            if Application.objects.filter(applicant=applicant).exists():
                skipped_apps += 1
                continue

            try:
                household_size = max(1, int(prof['household_size']))
            except (ValueError, TypeError):
                household_size = 1

            impact = (
                f"Extent of damage: {prof.get('extent_damage', 'N/A')}. "
                f"Household type: {prof.get('household_type', 'N/A')}. "
                f"Tenurial status: {prof.get('tenurial_stat', 'N/A')}. "
                f"Housing option: {prof.get('housing_option', 'N/A')}."
            )

            Application.objects.create(
                applicant=applicant,
                full_name=full_name or applicant.get_full_name() or applicant.username,
                family_size=household_size,
                current_address=prof.get('place_origin', ''),
                impact_description=impact,
                status='approved',
                submission_date=timezone.now(),
                notes=f"Imported. Contact: {prof.get('contact_no', '')}",
            )
            created_apps += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'Users (extra from profiles): {created_users}  '
                f'Applications: created={created_apps}, skipped={skipped_apps}'
            )
        )

        # ── 3. Update house allocations ──────────────────────────────────
        allocated_count = 0
        alloc_skipped   = 0

        for ref_id, prof in profiles_sql.items():
            receiving_add = prof.get('receiving_add', '').strip()
            if not receiving_add or not receiving_add.startswith('Block'):
                alloc_skipped += 1
                continue

            house = (
                House.objects.filter(house_number=receiving_add, site=1).first()
                or House.objects.filter(house_number=receiving_add, site=2).first()
            )
            if not house:
                alloc_skipped += 1
                continue

            applicant = ref_to_applicant.get(ref_id)
            if not applicant:
                alloc_skipped += 1
                continue

            # Only allocate if house is not already taken by someone else
            if house.allocated_to and house.allocated_to != applicant:
                alloc_skipped += 1
                continue

            house.allocated_to    = applicant
            house.status          = 'occupied'
            house.allocation_date = timezone.now().date()
            house.save(update_fields=['allocated_to', 'status', 'allocation_date'])
            allocated_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f'House allocations: updated={allocated_count}, skipped={alloc_skipped}'
            )
        )

        self.stdout.write(self.style.SUCCESS('\nImport complete.'))
        self.stdout.write(
            'Default password for all imported users is their username in lowercase.\n'
            'Example: username "Admin" => password "admin"'
        )
