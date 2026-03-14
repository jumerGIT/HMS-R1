from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('housing', '0004_expand_application_fields'),
    ]

    operations = [
        migrations.CreateModel(
            name='HouseholdMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fname', models.CharField(max_length=100, verbose_name='First name')),
                ('mname', models.CharField(blank=True, max_length=100, verbose_name='Middle name')),
                ('lname', models.CharField(max_length=100, verbose_name='Last name')),
                ('relationship', models.CharField(
                    choices=[
                        ('spouse', 'Spouse'), ('child', 'Child'),
                        ('parent', 'Parent'), ('sibling', 'Sibling'),
                        ('grandchild', 'Grandchild'), ('grandparent', 'Grandparent'),
                        ('other_relative', 'Other Relative'), ('non_relative', 'Non-Relative'),
                    ],
                    default='other_relative', max_length=20,
                )),
                ('bdate', models.DateField(blank=True, null=True, verbose_name='Birthdate')),
                ('application', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='members',
                    to='housing.application',
                )),
            ],
            options={
                'ordering': ['lname', 'fname'],
            },
        ),
    ]
