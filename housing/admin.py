"""
Django admin customization for the Housing Management System.
"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.utils import timezone
from .models import CustomUser, House, Application, AllocationHistory


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = [
        'username', 'email', 'first_name', 'last_name',
        'role', 'phone', 'is_active', 'date_joined',
    ]
    list_filter = ['role', 'is_active', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name', 'phone']
    ordering = ['role', 'username']

    fieldsets = UserAdmin.fieldsets + (
        ('Housing System', {
            'fields': ('role', 'phone', 'address'),
        }),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Housing System', {
            'fields': ('role', 'phone', 'address'),
        }),
    )


@admin.register(House)
class HouseAdmin(admin.ModelAdmin):
    list_display = [
        'house_number', 'svg_id', 'status_badge',
        'allocated_to', 'allocation_date',
    ]
    list_filter = ['status']
    search_fields = ['house_number', 'allocated_to__username']
    raw_id_fields = ['allocated_to']

    def save_model(self, request, obj, form, change):
        # Detect if allocated_to just got assigned (new or changed)
        previous_allocated_to = None
        if change:
            try:
                previous_allocated_to = House.objects.get(pk=obj.pk).allocated_to
            except House.DoesNotExist:
                pass

        super().save_model(request, obj, form, change)

        # Create history record if allocated_to was newly set
        if obj.allocated_to and obj.allocated_to != previous_allocated_to:
            if not obj.allocation_date:
                obj.allocation_date = timezone.now().date()
                House.objects.filter(pk=obj.pk).update(allocation_date=obj.allocation_date)
            AllocationHistory.objects.create(
                house=obj,
                beneficiary=obj.allocated_to,
                allocated_by=request.user,
            )

    def status_badge(self, obj):
        color = 'green' if obj.status == 'available' else 'red'
        return format_html(
            '<span style="color:white;background:{};padding:2px 8px;border-radius:4px">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = [
        'full_name', 'applicant', 'family_size',
        'status', 'submission_date', 'reviewed_by', 'review_date',
    ]
    list_filter = ['status', 'submission_date']
    search_fields = ['full_name', 'applicant__username', 'current_address']
    raw_id_fields = ['applicant', 'reviewed_by']
    readonly_fields = ['submission_date']


@admin.register(AllocationHistory)
class AllocationHistoryAdmin(admin.ModelAdmin):
    list_display = ['house', 'beneficiary', 'allocated_by', 'date']
    list_filter = ['date']
    search_fields = ['house__house_number', 'beneficiary__username']
    readonly_fields = ['date']
