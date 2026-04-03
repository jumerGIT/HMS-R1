"""
Django forms for template-based views.
"""
import re
from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Application, House


# ---------------------------------------------------------------------------
# Shared birthdate validation helper
# ---------------------------------------------------------------------------
_MIN_BIRTH_YEAR = 1900


def _validate_birthdate(value, min_age=None, field_label='Birthdate'):
    """
    Raise ValidationError if:
      - Year is before 1900
      - Date is in the future
      - Age is below min_age (if supplied)
    Returns the validated date unchanged.
    """
    if not value:
        return value
    today = date.today()
    if value.year < _MIN_BIRTH_YEAR:
        raise forms.ValidationError(f'{field_label} year cannot be before {_MIN_BIRTH_YEAR}.')
    if value > today:
        raise forms.ValidationError(f'{field_label} cannot be in the future.')
    if min_age is not None:
        age = today.year - value.year - (
            (today.month, today.day) < (value.month, value.day)
        )
        if age < min_age:
            raise forms.ValidationError(
                f'{field_label} indicates an age below {min_age}. '
                f'The household head must be at least {min_age} years old.'
            )
    return value


# ---------------------------------------------------------------------------
# Shared custom fields
# ---------------------------------------------------------------------------
class PhilippinePhoneField(forms.CharField):
    """
    Accepts PH mobile/landline in any common format and normalises to +63XXXXXXXXXX.
    Valid inputs: 09171234567, 9171234567, +639171234567, 0917-123-4567, etc.
    Displayed without the +63 prefix so the user only types the 10-digit number.
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('max_length', 20)
        kwargs.setdefault('required', False)
        super().__init__(*args, **kwargs)

    def prepare_value(self, value):
        """Strip +63 so the input field shows just the 10-digit number."""
        if value and str(value).startswith('+63'):
            return str(value)[3:]
        return value or ''

    def clean(self, value):
        value = super().clean(value)
        if not value:
            return value
        # Strip whitespace, dashes, dots, parentheses
        digits = re.sub(r'[\s\-\(\)\.]', '', value)
        # Strip country-code prefix if provided
        if digits.startswith('+63'):
            digits = digits[3:]
        elif digits.startswith('0'):
            digits = digits[1:]
        # Must be exactly 10 digits, first digit 2–9 (PH mobile starts with 9)
        if not re.match(r'^[2-9]\d{9}$', digits):
            raise forms.ValidationError(
                'Enter a valid Philippine phone number (e.g. 9171234567).'
            )
        return f'+63{digits}'


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
class RegisterForm(UserCreationForm):
    """Self-registration form – always creates an applicant."""
    email      = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True)
    last_name  = forms.CharField(max_length=50, required=True)
    phone      = PhilippinePhoneField(required=False, label='Phone')

    class Meta:
        model  = CustomUser
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'phone', 'password1', 'password2',
        ]

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if CustomUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('This email address is already registered.')
        return email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role  = 'applicant'
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        if commit:
            user.save()
        return user


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
_MAX_IMAGE_BYTES = 5 * 1024 * 1024   # 5 MB
_ALLOWED_IMAGE_TYPES = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}


class ApplicationForm(forms.ModelForm):
    """Form for applicants to submit/edit their application."""
    contact_no = PhilippinePhoneField(required=False, label='Contact Number')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['hh_bdate'].required = True

    class Meta:
        model  = Application
        fields = [
            # Applicant name
            'applicant_fname', 'applicant_lname',
            # Household head
            'hh_fname', 'hh_mname', 'hh_lname', 'hh_bdate', 'hh_image',
            # National ID
            'national_id_front', 'national_id_back',
            # Civil status / spouse
            'civil_status', 'spouse_name', 'spouse_bdate',
            # Household details
            'household_type', 'tenurial_status',
            'extent_damage', 'housing_option', 'monthly_income',
            # Address / contact
            'current_address', 'contact_no',
        ]
        widgets = {
            'hh_bdate':     forms.DateInput(attrs={
                'type': 'date',
                'min': f'{_MIN_BIRTH_YEAR}-01-01',
                'max': date.today().isoformat(),
            }),
            'spouse_bdate': forms.DateInput(attrs={
                'type': 'date',
                'min': f'{_MIN_BIRTH_YEAR}-01-01',
                'max': date.today().isoformat(),
            }),
            'current_address': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'applicant_fname': 'Your First Name',
            'applicant_lname': 'Your Last Name',
            'hh_fname':        'First Name',
            'hh_mname':        'Middle Name',
            'hh_lname':        'Last Name',
            'hh_bdate':        'Birthdate',
            'hh_image':        'Photo (optional)',
            'civil_status':    'Civil Status',
            'spouse_name':     'Spouse Full Name',
            'spouse_bdate':    'Spouse Birthdate',
            'household_type':  'Type of Household',
            'tenurial_status': 'Tenurial Status',
            'family_size':     'Household Size',
            'extent_damage':   'Extent of Damage',
            'housing_option':  'Preferred Housing Option',
            'monthly_income':  'Monthly Income (PHP)',
            'current_address': 'Address / Place of Origin',
            'contact_no':      'Contact Number',
        }

    # ── Image validation ──────────────────────────────────────────────────
    def _validate_image(self, field_name):
        f = self.cleaned_data.get(field_name)
        if f and hasattr(f, 'size'):
            if f.size > _MAX_IMAGE_BYTES:
                raise forms.ValidationError('Image must be smaller than 5 MB.')
            content_type = getattr(f, 'content_type', '')
            if content_type and content_type not in _ALLOWED_IMAGE_TYPES:
                raise forms.ValidationError(
                    'Only JPEG, PNG, WebP, or GIF images are accepted.'
                )
        return f

    def clean_hh_bdate(self):
        return _validate_birthdate(
            self.cleaned_data.get('hh_bdate'),
            min_age=18,
            field_label='Household head birthdate',
        )

    def clean_spouse_bdate(self):
        return _validate_birthdate(
            self.cleaned_data.get('spouse_bdate'),
            field_label='Spouse birthdate',
        )

    def clean_hh_image(self):
        return self._validate_image('hh_image')

    def clean_national_id_front(self):
        return self._validate_image('national_id_front')

    def clean_national_id_back(self):
        return self._validate_image('national_id_back')


# ---------------------------------------------------------------------------
# House
# ---------------------------------------------------------------------------
class AddHouseForm(forms.ModelForm):
    """Form for admin/housing incharge to manually add a house."""

    class Meta:
        model  = House
        fields = ['site', 'house_number', 'status', 'coordinates']
        widgets = {
            'house_number': forms.TextInput(attrs={'placeholder': 'Block No. 1 | Lot No. 1'}),
            'coordinates':  forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'SVG path data, e.g. M98.29,246.24l-15.93,1.49…z',
            }),
        }
        labels = {
            'house_number': 'House Address (Block / Lot)',
            'site':         'Site',
            'status':       'Status',
            'coordinates':  'SVG Coordinates (optional)',
        }


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------
class ReviewApplicationForm(forms.ModelForm):
    """Form for Beneficiary Incharge to approve/reject an application."""

    class Meta:
        model   = Application
        fields  = ['status', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show approve/reject options (not pending)
        self.fields['status'].choices = [
            ('pending',  'Keep Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ]
