from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('housing', '0006_national_id_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='customuser',
            name='must_change_password',
            field=models.BooleanField(
                default=False,
                help_text='Force user to change password on next login',
            ),
        ),
    ]
