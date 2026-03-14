"""
DRF Serializers for the Housing Management System.
"""
from rest_framework import serializers
from .models import CustomUser, House, Application, AllocationHistory


class UserSerializer(serializers.ModelSerializer):
    """Full user serializer – admin only."""

    class Meta:
        model = CustomUser
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'role', 'phone', 'address', 'is_active', 'date_joined',
        ]
        read_only_fields = ['date_joined']


class UserMinimalSerializer(serializers.ModelSerializer):
    """
    Minimal user info used inside House serializer.
    Exposes only what Housing Incharge needs – no sensitive applicant data.
    """

    class Meta:
        model = CustomUser
        fields = ['id', 'first_name', 'last_name', 'username']


class HouseSerializer(serializers.ModelSerializer):
    """House serializer. Allocated user shown with minimal info only."""
    allocated_to_detail = UserMinimalSerializer(
        source='allocated_to', read_only=True
    )

    class Meta:
        model = House
        fields = [
            'id', 'house_number', 'site', 'status', 'svg_id',
            'coordinates', 'allocated_to', 'allocated_to_detail',
            'allocation_date',
        ]


class ApplicationSerializer(serializers.ModelSerializer):
    """Application serializer – for beneficiary incharge / admin."""
    applicant_username = serializers.CharField(
        source='applicant.username', read_only=True
    )
    reviewed_by_username = serializers.CharField(
        source='reviewed_by.username', read_only=True
    )

    class Meta:
        model = Application
        fields = [
            'id', 'applicant', 'applicant_username',
            'full_name', 'family_size', 'current_address',
            'impact_description', 'submission_date',
            'status', 'reviewed_by', 'reviewed_by_username',
            'review_date', 'notes',
        ]
        read_only_fields = ['submission_date', 'applicant']


class MyApplicationSerializer(serializers.ModelSerializer):
    """
    Applicant's own application – read/write their own data.
    Status, reviewer, and review date are read-only for applicants.
    """

    class Meta:
        model = Application
        fields = [
            'id', 'full_name', 'family_size', 'current_address',
            'impact_description', 'submission_date',
            'status', 'review_date', 'notes',
        ]
        read_only_fields = ['submission_date', 'status', 'review_date', 'notes']


class AllocateSerializer(serializers.Serializer):
    """
    Used by POST /api/allocate/ to assign a house to an approved applicant.
    Only accepts applicants whose application status is 'approved'.
    """
    house_id = serializers.PrimaryKeyRelatedField(
        queryset=House.objects.filter(status='available')
    )
    applicant_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomUser.objects.filter(role='applicant')
    )

    def validate(self, data):
        applicant = data['applicant_id']
        # Housing Incharge can only allocate APPROVED applicants
        try:
            app = applicant.application
            if app.status != 'approved':
                raise serializers.ValidationError(
                    'Applicant must have an approved application before allocation.'
                )
        except Application.DoesNotExist:
            raise serializers.ValidationError(
                'This applicant has not submitted an application.'
            )
        # Ensure applicant does not already have a house
        if House.objects.filter(allocated_to=applicant).exists():
            raise serializers.ValidationError(
                'This applicant already has a house allocated.'
            )
        return data


class AllocationHistorySerializer(serializers.ModelSerializer):
    house_number = serializers.CharField(source='house.house_number', read_only=True)
    beneficiary_name = serializers.CharField(
        source='beneficiary.get_full_name', read_only=True
    )
    allocated_by_name = serializers.CharField(
        source='allocated_by.get_full_name', read_only=True
    )

    class Meta:
        model = AllocationHistory
        fields = [
            'id', 'house_number', 'beneficiary_name',
            'allocated_by_name', 'date',
        ]


class ApprovedApplicantSerializer(serializers.ModelSerializer):
    """
    Minimal serializer for Housing Incharge's allocation dropdown.
    Only exposes approved applicants – no sensitive personal data beyond name.
    """
    full_name = serializers.SerializerMethodField()
    application_id = serializers.IntegerField(source='application.id', read_only=True)

    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'full_name', 'application_id']

    def get_full_name(self, obj):
        # Pull name from the application record, not user profile
        try:
            return obj.application.full_name
        except Application.DoesNotExist:
            return obj.get_full_name() or obj.username
