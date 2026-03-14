"""
Django forms for template-based views.
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Application, House


class RegisterForm(UserCreationForm):
    """Self-registration form – always creates an applicant."""
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    phone = forms.CharField(max_length=20, required=False)

    class Meta:
        model = CustomUser
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'phone', 'password1', 'password2',
        ]

    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = 'applicant'  # Registration always creates applicants
        user.email = self.cleaned_data['email']
        user.phone = self.cleaned_data.get('phone', '')
        if commit:
            user.save()
        return user


class ApplicationForm(forms.ModelForm):
    """Form for applicants to submit/edit their application."""

    class Meta:
        model = Application
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
            'hh_bdate':     forms.DateInput(attrs={'type': 'date'}),
            'spouse_bdate': forms.DateInput(attrs={'type': 'date'}),
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


class AddHouseForm(forms.ModelForm):
    """Form for admin/housing incharge to manually add a house."""

    class Meta:
        model = House
        fields = ['site', 'house_number', 'status', 'coordinates']
        widgets = {
            'house_number': forms.TextInput(attrs={'placeholder': 'Block No. 1 | Lot No. 1'}),
            'coordinates': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'SVG path data, e.g. M98.29,246.24l-15.93,1.49…z',
            }),
        }
        labels = {
            'house_number': 'House Address (Block / Lot)',
            'site': 'Site',
            'status': 'Status',
            'coordinates': 'SVG Coordinates (optional)',
        }


class ReviewApplicationForm(forms.ModelForm):
    """Form for Beneficiary Incharge to approve/reject an application."""

    class Meta:
        model = Application
        fields = ['status', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show approve/reject options (not pending)
        self.fields['status'].choices = [
            ('pending', 'Keep Pending'),
            ('approved', 'Approved'),
            ('rejected', 'Rejected'),
        ]
