import django.db.models.deletion
import django.utils.timezone
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('housing', '0012_walkin_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='ActivityLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('action', models.CharField(
                    choices=[
                        ('login',              'Login'),
                        ('logout',             'Logout'),
                        ('register',           'Registration'),
                        ('change_password',    'Password Change'),
                        ('add_house',          'Add House'),
                        ('import_houses',      'Import Houses'),
                        ('allocate_house',     'Allocate House'),
                        ('review_application', 'Review Application'),
                        ('walkin_entry',       'Walk-in Entry'),
                        ('create_user',        'Create User'),
                        ('update_user',        'Update User'),
                        ('toggle_user',        'Toggle User Active'),
                        ('delete_user',        'Delete User'),
                    ],
                    max_length=30,
                )),
                ('description', models.TextField()),
                ('ip_address', models.GenericIPAddressField(blank=True, null=True)),
                ('timestamp', models.DateTimeField(default=django.utils.timezone.now)),
                ('user', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='activity_logs',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'verbose_name': 'Activity Log',
                'verbose_name_plural': 'Activity Logs',
                'ordering': ['-timestamp'],
            },
        ),
    ]
