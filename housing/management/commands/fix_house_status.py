from django.core.management.base import BaseCommand
from housing.models import House

class Command(BaseCommand):
    help = 'Fix inconsistent house status based on allocated_to field'

    def handle(self, *args, **options):
        # Fix houses where status='occupied' but no allocated_to
        fixed_available = House.objects.filter(status='occupied', allocated_to__isnull=True).update(
            status='available'
        )
        
        # Fix houses where status='available' but has allocated_to
        fixed_occupied = House.objects.filter(status='available', allocated_to__isnull=False).update(
            status='occupied'
        )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Fixed {fixed_available} "occupied→available" + {fixed_occupied} "available→occupied"'
            )
        )

