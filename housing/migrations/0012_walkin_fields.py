from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('housing', '0011_seed_sending_areas'),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='is_walkin',
            field=models.BooleanField(
                default=False,
                help_text='True when a staff member encoded this on behalf of a walk-in applicant',
            ),
        ),
        migrations.AddField(
            model_name='application',
            name='entered_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='entered_applications',
                limit_choices_to={'role__in': ['admin', 'beneficiary_incharge']},
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
