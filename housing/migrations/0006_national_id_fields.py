from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('housing', '0005_householdmember'),
    ]

    operations = [
        migrations.AddField(
            model_name='application',
            name='national_id_front',
            field=models.ImageField(blank=True, upload_to='applicants/ids/', verbose_name='National ID – Front'),
        ),
        migrations.AddField(
            model_name='application',
            name='national_id_back',
            field=models.ImageField(blank=True, upload_to='applicants/ids/', verbose_name='National ID – Back'),
        ),
    ]
