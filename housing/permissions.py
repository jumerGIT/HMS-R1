"""
Custom DRF permission classes for the Housing Management System.
Each permission strictly enforces role boundaries.
"""
from rest_framework.permissions import BasePermission


class IsAdminRole(BasePermission):
    """Only users with role='admin' are allowed."""
    message = 'Access restricted to Admin users only.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'admin'
        )


class IsHousingIncharge(BasePermission):
    """
    Allowed roles: admin, housing_incharge.
    Housing incharges manage houses and allocations ONLY.
    They must NOT see applicant personal data.
    """
    message = 'Access restricted to Housing Incharge or Admin.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in ('admin', 'housing_incharge')
        )


class IsBeneficiaryIncharge(BasePermission):
    """
    Allowed roles: admin, beneficiary_incharge.
    Beneficiary incharges manage applications ONLY.
    They must NOT see house or allocation data.
    """
    message = 'Access restricted to Beneficiary Incharge or Admin.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in ('admin', 'beneficiary_incharge')
        )


class IsApplicant(BasePermission):
    """Only applicants can access their own application endpoint."""
    message = 'Access restricted to Applicant users.'

    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role == 'applicant'
        )


class IsOwnerApplicant(BasePermission):
    """
    Object-level permission: applicant can only access their own application.
    """
    message = 'You can only view your own application.'

    def has_object_permission(self, request, view, obj):
        return obj.applicant == request.user
