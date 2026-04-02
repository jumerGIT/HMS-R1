"""
URL patterns for the housing app (template views).
"""
from django.urls import path
from . import views

urlpatterns = [
    # Auth
    path('', views.dashboard, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),

    # Dashboards
    path('dashboard/', views.dashboard, name='dashboard'),
    path('change-password/', views.change_password, name='change_password'),
    path('dashboard/admin/', views.admin_dashboard, name='admin_dashboard'),
    path('dashboard/housing/', views.housing_dashboard, name='housing_dashboard'),
    path('dashboard/beneficiary/', views.beneficiary_dashboard, name='beneficiary_dashboard'),
    path('dashboard/applicant/', views.applicant_dashboard, name='applicant_dashboard'),

    # Houses (Housing Incharge + Admin)
    path('houses/', views.house_list, name='house_list'),
    path('houses/add/', views.add_house, name='add_house'),
    path('houses/import/', views.import_houses_csv, name='import_houses_csv'),
    path('houses/<uuid:pk>/detail/', views.house_detail_json, name='house_detail_json'),
    path('map/', views.map_view, name='map'),

    # Applications (Beneficiary Incharge + Admin)
    path('applications/', views.application_list, name='application_list'),
    path('applications/walkin/', views.walkin_application, name='walkin_application'),
    path('applications/<uuid:pk>/', views.application_detail, name='application_detail'),
    path('applications/<uuid:pk>/allocate/', views.allocate_house, name='allocate_house'),
    path('api/houses/by-site/<int:site_number>/', views.houses_by_site, name='houses_by_site'),
    path('api/stats/', views.api_dashboard_stats, name='api_dashboard_stats'),

    # Applicant views
    path('my-application/', views.my_application, name='my_application'),
    path('member-search/', views.member_search, name='member_search'),

    # Housed beneficiaries directory
    path('housed/', views.housed_list, name='housed_list'),
    path('housed/hh/<uuid:pk>/update-name/', views.beneficiary_update_name, name='beneficiary_update_name'),
    path('housed/member/<uuid:pk>/update-name/', views.member_update_name, name='member_update_name'),

    # Admin user management
    path('users/', views.user_management, name='user_management'),
    path('users/create/', views.create_staff_user, name='create_staff_user'),
    path('users/<uuid:pk>/toggle/', views.toggle_user_active, name='toggle_user_active'),
    path('users/<uuid:pk>/edit/', views.update_user, name='update_user'),
    path('users/<uuid:pk>/delete/', views.delete_user, name='delete_user'),

    # Activity log (admin only)
    path('activity-log/', views.activity_log_view, name='activity_log'),
]
