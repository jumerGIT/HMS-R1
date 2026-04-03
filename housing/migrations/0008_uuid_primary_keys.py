import uuid

from django.db import migrations, models


def convert_pks_to_uuid(apps, schema_editor):
    """
    PostgreSQL-only: converts PK and FK columns from bigint → uuid.

    PostgreSQL cannot cast bigint directly to uuid; we use gen_random_uuid()
    instead.  Since the database is always empty at this point (fresh deploy),
    the random values assigned here don't matter.

    SQLite handles the conversion automatically via table-recreation inside the
    AlterField operations that follow this RunPython, so this function is a
    no-op for any non-PostgreSQL backend.
    """
    if schema_editor.connection.vendor != 'postgresql':
        return

    with schema_editor.connection.cursor() as cursor:
        # ── Step 1: drop every FK constraint that references the tables whose
        #            PKs we are about to change.  We use a DO block so we can
        #            loop over information_schema results inside a single round-
        #            trip.  IF EXISTS prevents errors if a constraint was
        #            already removed for any reason.
        cursor.execute("""
            DO $$
            DECLARE r RECORD;
            BEGIN
                FOR r IN (
                    SELECT DISTINCT tc.constraint_name, tc.table_name
                    FROM information_schema.table_constraints  tc
                    JOIN information_schema.referential_constraints rc
                        ON  tc.constraint_name = rc.constraint_name
                    JOIN information_schema.table_constraints  tc_ref
                        ON  rc.unique_constraint_name = tc_ref.constraint_name
                    WHERE tc.constraint_type = 'FOREIGN KEY'
                      AND tc.table_schema    = 'public'
                      AND tc_ref.table_schema = 'public'
                      AND tc_ref.table_name IN (
                            'housing_customuser',
                            'housing_house',
                            'housing_application',
                            'housing_householdmember',
                            'housing_allocationhistory'
                          )
                )
                LOOP
                    EXECUTE format(
                        'ALTER TABLE %I DROP CONSTRAINT IF EXISTS %I',
                        r.table_name, r.constraint_name
                    );
                END LOOP;
            END $$;
        """)

        # ── Step 2: convert PK columns to uuid.
        for table in [
            'housing_customuser',
            'housing_house',
            'housing_application',
            'housing_householdmember',
            'housing_allocationhistory',
        ]:
            cursor.execute(
                f'ALTER TABLE "{table}" '
                f'ALTER COLUMN "id" TYPE uuid USING gen_random_uuid()'
            )

        # ── Step 3: convert FK columns that pointed at those PKs.
        #            After the type change above the FK columns are still
        #            bigint; change them to uuid as well.
        fk_columns = [
            ('housing_house',             'allocated_to_id'),
            ('housing_application',       'applicant_id'),
            ('housing_application',       'reviewed_by_id'),
            ('housing_allocationhistory', 'house_id'),
            ('housing_allocationhistory', 'beneficiary_id'),
            ('housing_allocationhistory', 'allocated_by_id'),
            ('housing_householdmember',   'application_id'),
            # Django M2M through-tables for CustomUser (groups, user_permissions)
            ('housing_customuser_groups',           'customuser_id'),
            ('housing_customuser_user_permissions', 'customuser_id'),
        ]

        # authtoken_token is present when rest_framework.authtoken is installed;
        # check before touching it.
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_name   = 'authtoken_token'
            )
        """)
        if cursor.fetchone()[0]:
            fk_columns.append(('authtoken_token', 'user_id'))

        for table, col in fk_columns:
            # Guard: only change columns that are still bigint (idempotency).
            cursor.execute("""
                SELECT data_type
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name   = %s
                  AND column_name  = %s
            """, [table, col])
            row = cursor.fetchone()
            if row and row[0] != 'uuid':
                cursor.execute(
                    f'ALTER TABLE "{table}" '
                    f'ALTER COLUMN "{col}" TYPE uuid USING gen_random_uuid()'
                )

        # FK constraints are intentionally NOT re-added here.
        # The AlterField operations below will introspect the database (finding
        # no existing FK constraints), change the column types a second time
        # (uuid → uuid via "col"::uuid, which is a valid no-op cast on PG),
        # and then recreate all FK constraints with the correct Django-generated
        # names.


class Migration(migrations.Migration):
    """
    Switches all model primary keys from integer AutoField to UUIDField.

    PostgreSQL fix: AlterField generates USING "id"::uuid which fails for
    bigint → uuid.  A RunPython step runs first and uses gen_random_uuid()
    instead.  The subsequent AlterField operations are then effectively no-ops
    at the type-change level on PostgreSQL, but they handle Django's internal
    migration state and re-add FK constraints with their proper names.

    SQLite: RunPython is a no-op; AlterField handles conversion via the
    standard table-recreation approach.

    IMPORTANT: This migration requires a clean (empty) database.  Existing
    integer PK / FK values cannot be mapped to UUIDs; any data must be
    re-entered after applying this migration.
    """

    dependencies = [
        ('housing', '0007_customuser_must_change_password'),
    ]

    operations = [
        # Must run before AlterField on PostgreSQL.
        migrations.RunPython(convert_pks_to_uuid, migrations.RunPython.noop),

        # ── CustomUser ────────────────────────────────────────────────────────
        migrations.AlterField(
            model_name='customuser',
            name='id',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),

        # ── House ─────────────────────────────────────────────────────────────
        migrations.AlterField(
            model_name='house',
            name='id',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),

        # ── Application ───────────────────────────────────────────────────────
        migrations.AlterField(
            model_name='application',
            name='id',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),

        # ── HouseholdMember ───────────────────────────────────────────────────
        migrations.AlterField(
            model_name='householdmember',
            name='id',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),

        # ── AllocationHistory ─────────────────────────────────────────────────
        migrations.AlterField(
            model_name='allocationhistory',
            name='id',
            field=models.UUIDField(
                default=uuid.uuid4,
                editable=False,
                primary_key=True,
                serialize=False,
            ),
        ),
    ]
