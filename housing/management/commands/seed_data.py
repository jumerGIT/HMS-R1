"""
Management command: python manage.py seed_data

Creates:
  - 20 houses (H-001 to H-020)
  - 1 admin user
  - 1 housing incharge
  - 1 beneficiary incharge
  - 5 applicants with applications (3 approved, 1 rejected, 1 pending)
  - 2 allocations (houses H-001 and H-002 occupied)
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from housing.models import CustomUser, House, Application, AllocationHistory
from rest_framework.authtoken.models import Token


HOUSES = [
    {'number': f'H-{i:03d}', 'svg_id': f'house-{i:03d}'}
    for i in range(1, 21)
]

USERS = [
    {
        'username': 'admin_user',
        'password': 'Admin1234!',
        'first_name': 'Maria',
        'last_name': 'Santos',
        'email': 'admin@hms.local',
        'role': 'admin',
        'phone': '09171234567',
        'is_staff': True,
        'is_superuser': True,
    },
    {
        'username': 'housing1',
        'password': 'Housing1234!',
        'first_name': 'Jose',
        'last_name': 'Reyes',
        'email': 'housing@hms.local',
        'role': 'housing_incharge',
        'phone': '09181234567',
    },
    {
        'username': 'beneficiary1',
        'password': 'Beneficiary1234!',
        'first_name': 'Ana',
        'last_name': 'Cruz',
        'email': 'beneficiary@hms.local',
        'role': 'beneficiary_incharge',
        'phone': '09191234567',
    },
    {
        'username': 'applicant1',
        'password': 'Applicant1234!',
        'first_name': 'Pedro',
        'last_name': 'Garcia',
        'email': 'pedro@hms.local',
        'role': 'applicant',
        'phone': '09201111111',
    },
    {
        'username': 'applicant2',
        'password': 'Applicant1234!',
        'first_name': 'Luisa',
        'last_name': 'Dela Cruz',
        'email': 'luisa@hms.local',
        'role': 'applicant',
        'phone': '09202222222',
    },
    {
        'username': 'applicant3',
        'password': 'Applicant1234!',
        'first_name': 'Ramon',
        'last_name': 'Villanueva',
        'email': 'ramon@hms.local',
        'role': 'applicant',
        'phone': '09203333333',
    },
    {
        'username': 'applicant4',
        'password': 'Applicant1234!',
        'first_name': 'Celia',
        'last_name': 'Bautista',
        'email': 'celia@hms.local',
        'role': 'applicant',
        'phone': '09204444444',
    },
    {
        'username': 'applicant5',
        'password': 'Applicant1234!',
        'first_name': 'Eduardo',
        'last_name': 'Mendoza',
        'email': 'eduardo@hms.local',
        'role': 'applicant',
        'phone': '09205555555',
    },
]

APPLICATIONS = [
    {
        'username': 'applicant1',
        'full_name': 'Pedro Garcia',
        'family_size': 4,
        'current_address': 'Purok 3, Brgy. San Roque, Tacloban City',
        'impact': (
            'Our house in Barangay San Roque was completely destroyed by '
            'Typhoon Yolanda. My family of four has been living in a '
            'temporary shelter made of tarpaulin since November 2013. '
            'We lost everything – furniture, clothing, and our source of income.'
        ),
        'status': 'approved',
    },
    {
        'username': 'applicant2',
        'full_name': 'Luisa Dela Cruz',
        'family_size': 6,
        'current_address': 'Brgy. Palo, Leyte',
        'impact': (
            'The storm surge swept away our entire barangay. My husband '
            'and I have six children. We are currently renting a small room '
            'with three other families. Two of my children had to stop '
            'schooling because we could not afford the expenses.'
        ),
        'status': 'approved',
    },
    {
        'username': 'applicant3',
        'full_name': 'Ramon Villanueva',
        'family_size': 3,
        'current_address': 'Evac Center, Tacloban City',
        'impact': (
            'I am a widower raising two children alone. Our home was '
            'completely submerged during the typhoon. I have been staying '
            'at the evacuation center ever since. My eldest child has asthma '
            'and the conditions at the evacuation center are affecting her health.'
        ),
        'status': 'approved',
    },
    {
        'username': 'applicant4',
        'full_name': 'Celia Bautista',
        'family_size': 2,
        'current_address': 'Brgy. Marasbaras, Tacloban City',
        'impact': (
            'My application was submitted but I have not been able to '
            'provide the required documents yet due to illness.'
        ),
        'status': 'rejected',
        'notes': 'Incomplete documentation. Please resubmit with complete barangay certificate.',
    },
    {
        'username': 'applicant5',
        'full_name': 'Eduardo Mendoza',
        'family_size': 5,
        'current_address': 'Brgy. Abucay, Tacloban City',
        'impact': (
            'We lost our house and my father was injured during the typhoon. '
            'We are currently living with relatives but their house is also '
            'damaged. We urgently need permanent housing.'
        ),
        'status': 'pending',
    },
]


class Command(BaseCommand):
    help = 'Seed the database with initial houses, users, and applications'

    def handle(self, *args, **options):
        self.stdout.write('Creating houses...')
        for h in HOUSES:
            house, created = House.objects.get_or_create(
                house_number=h['number'],
                defaults={'svg_id': h['svg_id'], 'status': 'available'},
            )
            if created:
                self.stdout.write(f'  Created {house.house_number}')

        self.stdout.write('Creating users...')
        created_users = {}
        for u in USERS:
            if CustomUser.objects.filter(username=u['username']).exists():
                self.stdout.write(f'  Skipped {u["username"]} (already exists)')
                created_users[u['username']] = CustomUser.objects.get(username=u['username'])
                continue
            user = CustomUser.objects.create_user(
                username=u['username'],
                password=u['password'],
                first_name=u['first_name'],
                last_name=u['last_name'],
                email=u['email'],
                role=u['role'],
                phone=u.get('phone', ''),
                is_staff=u.get('is_staff', False),
                is_superuser=u.get('is_superuser', False),
            )
            Token.objects.get_or_create(user=user)
            created_users[user.username] = user
            self.stdout.write(f'  Created {user.username} ({user.role})')

        beneficiary_incharge = created_users.get('beneficiary1')

        self.stdout.write('Creating applications...')
        for app_data in APPLICATIONS:
            applicant = created_users.get(app_data['username'])
            if not applicant:
                continue
            if Application.objects.filter(applicant=applicant).exists():
                self.stdout.write(f'  Skipped application for {app_data["username"]}')
                continue
            app = Application.objects.create(
                applicant=applicant,
                full_name=app_data['full_name'],
                family_size=app_data['family_size'],
                current_address=app_data['current_address'],
                impact_description=app_data['impact'],
                status=app_data['status'],
                reviewed_by=beneficiary_incharge if app_data['status'] != 'pending' else None,
                review_date=timezone.now() if app_data['status'] != 'pending' else None,
                notes=app_data.get('notes', ''),
            )
            self.stdout.write(f'  Created application for {app_data["username"]} ({app.status})')

        self.stdout.write('Allocating houses to approved applicants...')
        housing_incharge = created_users.get('housing1')
        allocations = [
            ('H-001', 'applicant1'),
            ('H-002', 'applicant2'),
        ]
        for house_num, username in allocations:
            try:
                house = House.objects.get(house_number=house_num)
                applicant = created_users.get(username)
                if house.status == 'occupied':
                    self.stdout.write(f'  Skipped {house_num} (already occupied)')
                    continue
                house.allocated_to = applicant
                house.status = 'occupied'
                house.allocation_date = timezone.now().date()
                house.save()
                AllocationHistory.objects.create(
                    house=house,
                    beneficiary=applicant,
                    allocated_by=housing_incharge,
                )
                self.stdout.write(f'  Allocated {house_num} to {username}')
            except House.DoesNotExist:
                pass

        self.stdout.write(self.style.SUCCESS('\nSeed data created successfully!'))
        self.stdout.write('\nTest credentials:')
        for u in USERS:
            self.stdout.write(f'  {u["username"]:20s} / {u["password"]:20s}  ({u["role"]})')
