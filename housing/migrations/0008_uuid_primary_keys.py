import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    """
    Switches all model primary keys from integer AutoField to UUIDField.

    IMPORTANT: This migration requires a clean database.
    If you have existing data, run `python manage.py flush` (or delete the
    SQLite file) before applying, then re-seed. Changing PK types on rows
    that have integer FK references will break those relationships.
    """

    dependencies = [
        ('housing', '0007_customuser_must_change_password'),
    ]

    operations = [
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
