"""
API URL configuration (mounted at /api/ in root urls.py).
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api_views import (
    CustomObtainAuthToken,
    UserViewSet, HouseViewSet, ApplicationViewSet,
    MyApplicationView, ApprovedApplicantsView,
    AllocateView, AllocationHistoryView,
)

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'houses', HouseViewSet, basename='house')
router.register(r'applications', ApplicationViewSet, basename='application')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/', CustomObtainAuthToken.as_view(), name='api-token'),
    path('my-application/', MyApplicationView.as_view(), name='my-application'),
    path('approved-applicants/', ApprovedApplicantsView.as_view(), name='approved-applicants'),
    path('allocate/', AllocateView.as_view(), name='allocate'),
    path('allocation-history/', AllocationHistoryView.as_view(), name='allocation-history'),
]
