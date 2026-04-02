"""
Models for the Housing Management System.
Barangay Housing Village – Typhoon Haiyan (Yolanda) Relief Program
"""
import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class CustomUser(AbstractUser):
    """
    Extended user model with role-based access control.
    Roles determine what each user can see and do throughout the system.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('housing_incharge', 'Housing Incharge'),
        ('beneficiary_incharge', 'Beneficiary Incharge'),
        ('applicant', 'Applicant'),
    ]

    role = models.CharField(
        max_length=30,
        choices=ROLE_CHOICES,
        default='applicant',
        help_text='Determines system access level'
    )
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    must_change_password = models.BooleanField(
        default=False,
        help_text='Force user to change password on next login'
    )

    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    # --- Convenience role-check properties ---
    @property
    def is_admin_role(self):
        return self.role == 'admin'

    @property
    def is_housing_incharge(self):
        return self.role in ('admin', 'housing_incharge')

    @property
    def is_beneficiary_incharge(self):
        return self.role in ('admin', 'beneficiary_incharge')

    @property
    def is_applicant(self):
        return self.role == 'applicant'


class SendingArea(models.Model):
    """
    Represents a resettlement site (sending area).
    Used when allocating a house to a beneficiary.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    SITE_CHOICES = [(1, 'Site 1'), (2, 'Site 2')]

    site_number = models.IntegerField(choices=SITE_CHOICES, unique=True)
    name = models.CharField(max_length=150, help_text='E.g. Brgy. Old Poblacion')
    description = models.TextField(blank=True)

    class Meta:
        ordering = ['site_number']
        verbose_name = 'Sending Area'
        verbose_name_plural = 'Sending Areas'

    def __str__(self):
        return f"Site {self.site_number} – {self.name}"


class House(models.Model):
    """
    Represents one donated house in the village.
    Visibility: Admin + Housing Incharge only.
    Applicants and Beneficiary Incharges cannot see house data.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = [
        ('available', 'Available'),
        ('occupied', 'Occupied'),
    ]

    SITE_CHOICES = [(1, 'Site 1'), (2, 'Site 2')]

    house_number = models.CharField(
        max_length=100,
        help_text='E.g. Block No. 1 | Lot No. 1'
    )
    site = models.IntegerField(choices=SITE_CHOICES, default=1)
    status = models.CharField(
        max_length=10, choices=STATUS_CHOICES, default='available'
    )
    # svg_id matches the id attribute in the SVG map template
    svg_id = models.CharField(
        max_length=30, unique=True,
        help_text='Matches SVG element id, e.g. house-001'
    )
    coordinates = models.TextField(
        blank=True,
        help_text='SVG path data (d attribute)'
    )
    allocated_to = models.ForeignKey(
        CustomUser,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='allocated_house',
        # Only applicants can be allocated a house
        limit_choices_to={'role': 'applicant'},
    )
    allocation_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ['site', 'house_number']
        unique_together = [('site', 'house_number')]
        verbose_name = 'House'
        verbose_name_plural = 'Houses'

    def __str__(self):
        return f"{self.house_number} – {self.get_status_display()}"


class Application(models.Model):
    """
    A housing application submitted by an Applicant.
    Fields mirror tbl_applicant from the PHP project.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]
    CIVIL_STATUS_CHOICES = [
        ('single',    'Single'),
        ('married',   'Married'),
        ('widowed',   'Widowed'),
        ('separated', 'Separated'),
        ('live_in',   'Live-in / Cohabiting'),
    ]
    HOUSEHOLD_TYPE_CHOICES = [
        ('renter',             'Renter'),
        ('informal_settler',   'Informal Settler'),
        ('sharer',             'Sharer'),
        ('owner',              'Owner'),
        ('other',              'Other'),
    ]
    TENURIAL_CHOICES = [
        ('owner',   'Owner'),
        ('renter',  'Renter'),
        ('sharer',  'Sharer'),
        ('squatter','Squatter / Informal Settler'),
        ('other',   'Other'),
    ]
    DAMAGE_CHOICES = [
        ('totally_damaged',   'Totally Damaged'),
        ('partially_damaged', 'Partially Damaged'),
        ('minor_damage',      'Minor Damage'),
        ('no_damage',         'No Damage'),
    ]
    HOUSING_OPTION_CHOICES = [
        ('core_shelter',       'Core Shelter'),
        ('permanent_housing',  'Permanent Housing'),
        ('resettlement',       'Resettlement'),
        ('other',              'Other'),
    ]

    # ── Applicant link ──────────────────────────────────────────
    applicant = models.OneToOneField(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='application',
        limit_choices_to={'role': 'applicant'},
    )

    # ── Applicant name ─────────────────────────────────────────
    applicant_fname = models.CharField('First name', max_length=50, blank=True)
    applicant_lname = models.CharField('Last name', max_length=50, blank=True)

    # ── Household head ─────────────────────────────────────────
    hh_fname  = models.CharField('Head first name',  max_length=100, blank=True)
    hh_mname  = models.CharField('Head middle name', max_length=100, blank=True)
    hh_lname  = models.CharField('Head last name',   max_length=100, blank=True)
    hh_bdate  = models.DateField('Head birthdate', null=True, blank=True)
    hh_image        = models.ImageField('Head photo', upload_to='applicants/', blank=True)
    national_id_front = models.ImageField('National ID – Front', upload_to='applicants/ids/', blank=True)
    national_id_back  = models.ImageField('National ID – Back',  upload_to='applicants/ids/', blank=True)

    # ── Civil status / spouse ──────────────────────────────────
    civil_status = models.CharField(
        max_length=20, choices=CIVIL_STATUS_CHOICES, blank=True
    )
    spouse_name  = models.CharField('Spouse name', max_length=150, blank=True)
    spouse_bdate = models.DateField('Spouse birthdate', null=True, blank=True)

    # ── Household details ──────────────────────────────────────
    household_type   = models.CharField(max_length=30, choices=HOUSEHOLD_TYPE_CHOICES, blank=True)
    tenurial_status  = models.CharField(max_length=20, choices=TENURIAL_CHOICES, blank=True)
    family_size      = models.PositiveSmallIntegerField('Household size', default=1)
    extent_damage    = models.CharField(max_length=30, choices=DAMAGE_CHOICES, blank=True)
    housing_option   = models.CharField(max_length=30, choices=HOUSING_OPTION_CHOICES, blank=True)
    monthly_income   = models.PositiveIntegerField('Monthly income (PHP)', default=0)

    # ── Address / contact ──────────────────────────────────────
    current_address = models.TextField('Address / Place of origin')
    contact_no      = models.CharField('Contact number', max_length=30, blank=True)

    # ── Legacy / review fields ─────────────────────────────────
    full_name         = models.CharField(max_length=150, blank=True,
                            help_text='Auto-populated from household head name')
    impact_description = models.TextField(blank=True,
                            help_text='Legacy combined impact description (imported data)')
    submission_date   = models.DateTimeField(default=timezone.now)
    status            = models.CharField(
                            max_length=10, choices=STATUS_CHOICES, default='pending')
    reviewed_by       = models.ForeignKey(
                            CustomUser, null=True, blank=True,
                            on_delete=models.SET_NULL,
                            related_name='reviewed_applications',
                            limit_choices_to={'role__in': ['admin', 'beneficiary_incharge']})
    review_date = models.DateTimeField(null=True, blank=True)
    notes       = models.TextField(blank=True, help_text='Reviewer notes')

    # ── Walk-in tracking ───────────────────────────────────────────
    is_walkin  = models.BooleanField(
                    default=False,
                    help_text='True when a staff member encoded this on behalf of a walk-in applicant')
    entered_by = models.ForeignKey(
                    CustomUser, null=True, blank=True,
                    on_delete=models.SET_NULL,
                    related_name='entered_applications',
                    limit_choices_to={'role__in': ['admin', 'beneficiary_incharge']})

    class Meta:
        ordering = ['-submission_date']
        verbose_name = 'Application'
        verbose_name_plural = 'Applications'

    def save(self, *args, **kwargs):
        # Keep full_name in sync with household head name
        if self.hh_lname or self.hh_fname:
            parts = [self.hh_lname, self.hh_fname, self.hh_mname]
            self.full_name = ', '.join(p for p in parts if p).strip(', ')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Application by {self.full_name or self.applicant} – {self.get_status_display()}"


class HouseholdMember(models.Model):
    """A family/household member listed in an application."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    RELATIONSHIP_CHOICES = [
        ('spouse',         'Spouse'),
        ('child',          'Child'),
        ('parent',         'Parent'),
        ('sibling',        'Sibling'),
        ('grandchild',     'Grandchild'),
        ('grandparent',    'Grandparent'),
        ('other_relative', 'Other Relative'),
        ('non_relative',   'Non-Relative'),
    ]
    application  = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='members')
    fname        = models.CharField('First name', max_length=100)
    mname        = models.CharField('Middle name', max_length=100, blank=True)
    lname        = models.CharField('Last name', max_length=100)
    relationship = models.CharField(max_length=20, choices=RELATIONSHIP_CHOICES, default='other_relative')
    bdate        = models.DateField('Birthdate', null=True, blank=True)

    class Meta:
        ordering = ['lname', 'fname']

    def __str__(self):
        return f"{self.lname}, {self.fname} ({self.get_relationship_display()})"


class AllocationHistory(models.Model):
    """
    Audit log of every house allocation event.
    Useful for Admin reporting.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    house = models.ForeignKey(
        House, on_delete=models.CASCADE, related_name='history'
    )
    beneficiary = models.ForeignKey(
        CustomUser,
        on_delete=models.CASCADE,
        related_name='allocation_history',
    )
    allocated_by = models.ForeignKey(
        CustomUser,
        on_delete=models.SET_NULL,
        null=True,
        related_name='allocations_made',
    )
    date = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-date']
        verbose_name = 'Allocation History'
        verbose_name_plural = 'Allocation Histories'

    def __str__(self):
        return f"{self.house} → {self.beneficiary} on {self.date:%Y-%m-%d}"


class ActivityLog(models.Model):
    """
    Records every significant user action for admin audit purposes.
    Only admins can view this log.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    ACTION_CHOICES = [
        ('login',            'Login'),
        ('logout',           'Logout'),
        ('register',         'Registration'),
        ('change_password',  'Password Change'),
        ('add_house',        'Add House'),
        ('import_houses',    'Import Houses'),
        ('allocate_house',   'Allocate House'),
        ('review_application', 'Review Application'),
        ('walkin_entry',     'Walk-in Entry'),
        ('create_user',      'Create User'),
        ('update_user',      'Update User'),
        ('toggle_user',      'Toggle User Active'),
        ('delete_user',      'Delete User'),
    ]

    user = models.ForeignKey(
        CustomUser,
        null=True, blank=True,
        on_delete=models.SET_NULL,
        related_name='activity_logs',
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} – {self.get_action_display()}"
