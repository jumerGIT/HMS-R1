from django.db import migrations


def seed_sending_areas(apps, schema_editor):
    SendingArea = apps.get_model('housing', 'SendingArea')
    SendingArea.objects.bulk_create([
        SendingArea(site_number=1, name='Brgy. Old Poblacion'),
        SendingArea(site_number=2, name='Brgy. Washington'),
    ])


def reverse_seed(apps, schema_editor):
    apps.get_model('housing', 'SendingArea').objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ('housing', '0010_sending_area'),
    ]

    operations = [
        migrations.RunPython(seed_sending_areas, reverse_seed),
    ]
