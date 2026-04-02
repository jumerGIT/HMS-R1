"""
Django REST Framework API Views for the Housing Management System.

Endpoint summary:
  /api/houses/           – CRUD (Housing Incharge + Admin)
  /api/applications/     – CRUD (Beneficiary Incharge + Admin)
  /api/users/            – CRUD (Admin only)
  /api/allocate/         – POST to allocate house (Housing Incharge + Admin)
  /api/my-application/   – GET/POST/PATCH (Applicant only)
  /api/approved-applicants/ – GET list for allocation dropdown (Housing Incharge)
  /api/auth/token/       – Obtain auth token (login)
"""
from django.utils import timezone
from rest_framework import viewsets, generics, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token

from .models import ActivityLog, CustomUser, House, Application, AllocationHistory
from .permissions import (
    IsAdminRole, IsHousingIncharge, IsBeneficiaryIncharge, IsApplicant
)
from .serializers import (
    UserSerializer, HouseSerializer, ApplicationSerializer,
    MyApplicationSerializer, AllocateSerializer,
    AllocationHistorySerializer, ApprovedApplicantSerializer,
)


# ---------------------------------------------------------------------------
# Auth token endpoint (replaces default to return role info too)
# ---------------------------------------------------------------------------
class CustomObtainAuthToken(ObtainAuthToken):
    """Returns token + user role so the JS frontend can adapt UI."""

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        token = Token.objects.get(key=response.data['token'])
        user = token.user
        response.data['role'] = user.role
        response.data['user_id'] = user.id
        return response


# ---------------------------------------------------------------------------
# Users – Admin only
# ---------------------------------------------------------------------------
class UserViewSet(viewsets.ModelViewSet):
    """
    Full CRUD on users – restricted to Admin role only.
    No other role should be able to list or edit user accounts.
    """
    queryset = CustomUser.objects.all().order_by('date_joined')
    serializer_class = UserSerializer
    permission_classes = [IsAdminRole]


# ---------------------------------------------------------------------------
# Houses – Housing Incharge + Admin
# ---------------------------------------------------------------------------
class HouseViewSet(viewsets.ModelViewSet):
    """
    CRUD for houses.
    Accessible by Admin and Housing Incharge ONLY.
    Beneficiary Incharges and Applicants are forbidden from this endpoint.
    """
    queryset = House.objects.select_related('allocated_to').all()
    serializer_class = HouseSerializer
    permission_classes = [IsHousingIncharge]


# ---------------------------------------------------------------------------
# Applications – Beneficiary Incharge + Admin
# ---------------------------------------------------------------------------
class ApplicationViewSet(viewsets.ModelViewSet):
    """
    CRUD for applications.
    Accessible by Admin and Beneficiary Incharge ONLY.
    Housing Incharges cannot access this endpoint – they only see
    approved applicant names via /api/approved-applicants/.
    """
    queryset = Application.objects.select_related(
        'applicant', 'reviewed_by'
    ).all()
    serializer_class = ApplicationSerializer
    permission_classes = [IsBeneficiaryIncharge]

    def perform_update(self, serializer):
        # Auto-stamp reviewer and review date when status changes
        instance = serializer.save()
        if instance.status in ('approved', 'rejected') and not instance.reviewed_by:
            instance.reviewed_by = self.request.user
            instance.review_date = timezone.now()
            instance.save()


# ---------------------------------------------------------------------------
# My Application – Applicant only
# ---------------------------------------------------------------------------
class MyApplicationView(generics.RetrieveUpdateAPIView):
    """
    An applicant can GET and PATCH their own application.
    They cannot change status, reviewer, or review date – those fields
    are read-only in MyApplicationSerializer.
    """
    serializer_class = MyApplicationSerializer
    permission_classes = [IsApplicant]

    def get_object(self):
        try:
            return self.request.user.application
        except Application.DoesNotExist:
            return None

    def get(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj is None:
            return Response(
                {'detail': 'No application found. Please submit one.'},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = self.get_serializer(obj)
        return Response(serializer.data)

    def post(self, request, *args, **kwargs):
        """Create a new application for the logged-in applicant."""
        if Application.objects.filter(applicant=request.user).exists():
            return Response(
                {'detail': 'You already have an application.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(applicant=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    def patch(self, request, *args, **kwargs):
        obj = self.get_object()
        if obj is None:
            return Response(
                {'detail': 'No application found.'},
                status=status.HTTP_404_NOT_FOUND
            )
        if obj.status != 'pending':
            return Response(
                {'detail': 'You cannot edit an application that has already been reviewed.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        serializer = self.get_serializer(obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


# ---------------------------------------------------------------------------
# Approved Applicants – Housing Incharge uses this for the allocation dropdown
# NOTE: Only full_name (from application) and ID are exposed – no sensitive data
# ---------------------------------------------------------------------------
class ApprovedApplicantsView(generics.ListAPIView):
    """
    Returns applicants whose application is APPROVED and who don't yet have
    a house allocated. Housing Incharge uses this list in the SVG map modal.
    """
    serializer_class = ApprovedApplicantSerializer
    permission_classes = [IsHousingIncharge]

    def get_queryset(self):
        # Applicants with approved applications and no house allocated yet
        allocated_ids = House.objects.exclude(
            allocated_to=None
        ).values_list('allocated_to_id', flat=True)

        return CustomUser.objects.filter(
            role='applicant',
            application__status='approved',
        ).exclude(id__in=allocated_ids).select_related('application')


# ---------------------------------------------------------------------------
# Allocate – Housing Incharge + Admin
# ---------------------------------------------------------------------------
class AllocateView(APIView):
    """
    POST /api/allocate/
    Body: { "house_id": <int>, "applicant_id": <int> }

    Assigns a house to an approved applicant.
    Creates an AllocationHistory log entry.
    Only Housing Incharge (and Admin) can call this.
    """
    permission_classes = [IsHousingIncharge]

    def post(self, request):
        serializer = AllocateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        house = serializer.validated_data['house_id']
        applicant = serializer.validated_data['applicant_id']

        # Perform allocation
        house.allocated_to = applicant
        house.status = 'occupied'
        house.allocation_date = timezone.now().date()
        house.save()

        # Log the event
        AllocationHistory.objects.create(
            house=house,
            beneficiary=applicant,
            allocated_by=request.user,
        )

        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        ip = x_forwarded_for.split(',')[0].strip() if x_forwarded_for else request.META.get('REMOTE_ADDR')
        ActivityLog.objects.create(
            user=request.user,
            action='allocate_house',
            description=(
                f'House "{house.house_number}" (Site {house.site}) allocated to '
                f'"{applicant.get_full_name() or applicant.username}" via Map.'
            ),
            ip_address=ip,
        )

        return Response(
            {
                'detail': f'{house.house_number} successfully allocated to {applicant.get_full_name() or applicant.username}.',
                'house': HouseSerializer(house).data,
            },
            status=status.HTTP_200_OK,
        )


# ---------------------------------------------------------------------------
# Allocation History – Admin only
# ---------------------------------------------------------------------------
class AllocationHistoryView(generics.ListAPIView):
    """Read-only log of all allocations. Admin only."""
    queryset = AllocationHistory.objects.select_related(
        'house', 'beneficiary', 'allocated_by'
    ).all()
    serializer_class = AllocationHistorySerializer
    permission_classes = [IsAdminRole]
