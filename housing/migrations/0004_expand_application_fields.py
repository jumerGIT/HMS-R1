from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('housing', '0003_alter_house_options_alter_house_house_number_and_more'),
    ]

    operations = [
        # Applicant name fields
        migrations.AddField(
            model_name='application',
            name='applicant_fname',
            field=models.CharField(blank=True, max_length=50, verbose_name='First name'),
        ),
        migrations.AddField(
            model_name='application',
            name='applicant_lname',
            field=models.CharField(blank=True, max_length=50, verbose_name='Last name'),
        ),
        # Household head fields
        migrations.AddField(
            model_name='application',
            name='hh_fname',
            field=models.CharField(blank=True, max_length=100, verbose_name='Head first name'),
        ),
        migrations.AddField(
            model_name='application',
            name='hh_mname',
            field=models.CharField(blank=True, max_length=100, verbose_name='Head middle name'),
        ),
        migrations.AddField(
            model_name='application',
            name='hh_lname',
            field=models.CharField(blank=True, max_length=100, verbose_name='Head last name'),
        ),
        migrations.AddField(
            model_name='application',
            name='hh_bdate',
            field=models.DateField(blank=True, null=True, verbose_name='Head birthdate'),
        ),
        migrations.AddField(
            model_name='application',
            name='hh_image',
            field=models.ImageField(blank=True, upload_to='applicants/', verbose_name='Head photo'),
        ),
        # Civil status / spouse
        migrations.AddField(
            model_name='application',
            name='civil_status',
            field=models.CharField(
                blank=True, max_length=20,
                choices=[
                    ('single', 'Single'), ('married', 'Married'),
                    ('widowed', 'Widowed'), ('separated', 'Separated'),
                    ('live_in', 'Live-in / Cohabiting'),
                ],
            ),
        ),
        migrations.AddField(
            model_name='application',
            name='spouse_name',
            field=models.CharField(blank=True, max_length=150, verbose_name='Spouse name'),
        ),
        migrations.AddField(
            model_name='application',
            name='spouse_bdate',
            field=models.DateField(blank=True, null=True, verbose_name='Spouse birthdate'),
        ),
        # Household details
        migrations.AddField(
            model_name='application',
            name='household_type',
            field=models.CharField(
                blank=True, max_length=30,
                choices=[
                    ('renter', 'Renter'), ('informal_settler', 'Informal Settler'),
                    ('sharer', 'Sharer'), ('owner', 'Owner'), ('other', 'Other'),
                ],
            ),
        ),
        migrations.AddField(
            model_name='application',
            name='tenurial_status',
            field=models.CharField(
                blank=True, max_length=20,
                choices=[
                    ('owner', 'Owner'), ('renter', 'Renter'), ('sharer', 'Sharer'),
                    ('squatter', 'Squatter / Informal Settler'), ('other', 'Other'),
                ],
            ),
        ),
        migrations.AddField(
            model_name='application',
            name='extent_damage',
            field=models.CharField(
                blank=True, max_length=30,
                choices=[
                    ('totally_damaged', 'Totally Damaged'),
                    ('partially_damaged', 'Partially Damaged'),
                    ('minor_damage', 'Minor Damage'),
                    ('no_damage', 'No Damage'),
                ],
            ),
        ),
        migrations.AddField(
            model_name='application',
            name='housing_option',
            field=models.CharField(
                blank=True, max_length=30,
                choices=[
                    ('core_shelter', 'Core Shelter'),
                    ('permanent_housing', 'Permanent Housing'),
                    ('resettlement', 'Resettlement'),
                    ('other', 'Other'),
                ],
            ),
        ),
        migrations.AddField(
            model_name='application',
            name='monthly_income',
            field=models.PositiveIntegerField(default=0, verbose_name='Monthly income (PHP)'),
        ),
        migrations.AddField(
            model_name='application',
            name='contact_no',
            field=models.CharField(blank=True, max_length=30, verbose_name='Contact number'),
        ),
        # Make legacy fields optional
        migrations.AlterField(
            model_name='application',
            name='full_name',
            field=models.CharField(
                blank=True, max_length=150,
                help_text='Auto-populated from household head name',
            ),
        ),
        migrations.AlterField(
            model_name='application',
            name='current_address',
            field=models.TextField(verbose_name='Address / Place of origin'),
        ),
        migrations.AlterField(
            model_name='application',
            name='impact_description',
            field=models.TextField(
                blank=True,
                help_text='Legacy combined impact description (imported data)',
            ),
        ),
    ]
