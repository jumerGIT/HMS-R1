"""
Template-based views for the Housing Management System.
Role checks are enforced with decorators and explicit redirects.
"""
import base64
import re
import secrets
import string
import uuid
from io import BytesIO

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import ListView, DetailView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin

from django.http import HttpResponse

from .forms import AddHouseForm, ApplicationForm, RegisterForm, ReviewApplicationForm
from .models import ActivityLog, AllocationHistory, Application, CustomUser, House, HouseholdMember, SendingArea


# ---------------------------------------------------------------------------
# Activity logging helper
# ---------------------------------------------------------------------------
def _get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


def _parse_member_bdate(raw):
    """
    Parse and validate a member birthdate string (YYYY-MM-DD).
    Returns a date object, or None if blank.
    Raises ValueError with a human-readable message if invalid.
    """
    from datetime import date as _date
    if not raw:
        return None
    try:
        from datetime import datetime as _dt
        d = _dt.strptime(raw.strip(), '%Y-%m-%d').date()
    except ValueError:
        raise ValueError(f'Invalid date format: "{raw}".')
    if d.year < 1900:
        raise ValueError('Birthdate year cannot be before 1900.')
    if d > _date.today():
        raise ValueError('Birthdate cannot be in the future.')
    return d


def _normalize_ph_phone(raw):
    """
    Normalize any PH phone string to +63XXXXXXXXXX.
    Returns the original string unchanged if it doesn't match the PH format,
    so optional phone fields don't hard-fail on unexpected values.
    """
    import re as _re
    if not raw:
        return ''
    digits = _re.sub(r'[\s\-\(\)\.]', '', raw)
    if digits.startswith('+63'):
        digits = digits[3:]
    elif digits.startswith('0'):
        digits = digits[1:]
    if _re.match(r'^[2-9]\d{9}$', digits):
        return f'+63{digits}'
    return raw


def log_activity(request, action, description):
    """Record a user action to the ActivityLog table."""
    user = request.user if request.user.is_authenticated else None
    ActivityLog.objects.create(
        user=user,
        action=action,
        description=description,
        ip_address=_get_client_ip(request),
    )


# ---------------------------------------------------------------------------
# Health check (used by Railway deployment healthcheck)
# ---------------------------------------------------------------------------
def health(request):
    return HttpResponse('OK', content_type='text/plain')


# ---------------------------------------------------------------------------
# Helper decorators
# ---------------------------------------------------------------------------
def role_required(*roles):
    """
    Decorator factory that redirects to dashboard if the user's role
    is not in the allowed list.
    """
    def decorator(view_func):
        @login_required
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                messages.error(request, 'You do not have permission to view that page.')
                return redirect('dashboard')
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------
def login_view(request):
    """Standard login page. Redirects to dashboard if already logged in."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = AuthenticationForm(request, data=request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.get_user()
        login(request, user)
        log_activity(request, 'login', f'User "{user.username}" logged in.')
        return redirect('dashboard')
    return render(request, 'housing/login.html', {'form': form})


def logout_view(request):
    if request.user.is_authenticated:
        log_activity(request, 'logout', f'User "{request.user.username}" logged out.')
    logout(request)
    return redirect('login')


def register_view(request):
    """Public registration – creates an Applicant account."""
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegisterForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        log_activity(request, 'register', f'New applicant registered: "{user.username}" ({user.get_full_name()}).')
        messages.success(request, f'Welcome, {user.first_name}! Your applicant account has been created.')
        return redirect('dashboard')
    return render(request, 'housing/register.html', {'form': form})


# ---------------------------------------------------------------------------
# Dashboard – routes to role-specific dashboard
# ---------------------------------------------------------------------------
@login_required
def dashboard(request):
    user = request.user
    if user.must_change_password:
        return redirect('change_password')
    if user.role == 'admin':
        return redirect('admin_dashboard')
    elif user.role == 'housing_incharge':
        return redirect('housing_dashboard')
    elif user.role == 'beneficiary_incharge':
        return redirect('beneficiary_dashboard')
    else:
        return redirect('applicant_dashboard')


@login_required
def change_password(request):
    """Password change: forced (temp password) or voluntary (requires current password)."""
    user = request.user
    forced = user.must_change_password
    error = None
    if request.method == 'POST':
        new_pw  = request.POST.get('new_password', '')
        confirm = request.POST.get('confirm_password', '')
        if not forced:
            current = request.POST.get('current_password', '')
            if not user.check_password(current):
                error = 'Current password is incorrect.'
        if not error:
            if len(new_pw) < 8:
                error = 'New password must be at least 8 characters.'
            elif new_pw != confirm:
                error = 'Passwords do not match.'
            else:
                user.set_password(new_pw)
                user.must_change_password = False
                user.save()
                login(request, user)
                log_activity(request, 'change_password', f'User "{user.username}" changed their password.')
                messages.success(request, 'Password updated successfully.')
                return redirect('dashboard')
    return render(request, 'housing/change_password.html', {'error': error, 'forced': forced})


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------
@role_required('admin')
def admin_dashboard(request):
    import json as _json
    from datetime import date
    from django.db.models.functions import TruncMonth

    total_houses     = House.objects.count()
    available_houses = House.objects.filter(status='available').count()
    occupied_houses  = House.objects.filter(status='occupied').count()

    s1_avail = House.objects.filter(site=1, status='available').count()
    s1_occ   = House.objects.filter(site=1, status='occupied').count()
    s2_avail = House.objects.filter(site=2, status='available').count()
    s2_occ   = House.objects.filter(site=2, status='occupied').count()


    total_applications    = Application.objects.count()
    pending_applications  = Application.objects.filter(status='pending').count()
    approved_applications = Application.objects.filter(status='approved').count()
    rejected_applications = Application.objects.filter(status='rejected').count()
    pending_allocations   = Application.objects.filter(
        status='approved', applicant__allocated_house__isnull=True
    ).count()

    # Build the last 6 calendar months (current month + 5 prior), oldest first
    today = date.today()
    months = []
    for i in range(5, -1, -1):
        m, y = today.month - i, today.year
        while m <= 0:
            m += 12
            y -= 1
        months.append(date(y, m, 1))

    monthly_qs = (
        AllocationHistory.objects
        .filter(date__gte=months[0])
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    # TruncMonth returns datetime on Postgres; normalise to date(y, m, 1) as key
    monthly_dict = {}
    for row in monthly_qs:
        key = row['month']
        if hasattr(key, 'date'):   # datetime → date
            key = key.date()
        monthly_dict[key.replace(day=1)] = row['count']

    monthly_labels = [m.strftime('%b %Y') for m in months]
    monthly_data   = [monthly_dict.get(m, 0) for m in months]

    context = {
        'total_houses': total_houses,
        'available_houses': available_houses,
        'occupied_houses': occupied_houses,
        'total_applications': total_applications,
        'pending_applications': pending_applications,
        'approved_applications': approved_applications,
        'rejected_applications': rejected_applications,
        'pending_allocations': pending_allocations,
        'total_staff': CustomUser.objects.exclude(role='applicant').count(),
        'total_beneficiaries': CustomUser.objects.filter(role='applicant').count(),
        's1_avail': s1_avail, 's1_occ': s1_occ,
        's2_avail': s2_avail, 's2_occ': s2_occ,
        'monthly_labels_json': _json.dumps(monthly_labels),
        'monthly_data_json': _json.dumps(monthly_data),
        'recent_allocations': AllocationHistory.objects.select_related(
            'house', 'beneficiary', 'allocated_by'
        ).order_by('-date'),
    }
    return render(request, 'housing/dashboard_admin.html', context)


# ---------------------------------------------------------------------------
# Housing Incharge Dashboard
# Note: this view intentionally does NOT query Application or CustomUser
# personal data – Housing Incharge must not see applicant info.
# ---------------------------------------------------------------------------
@role_required('admin', 'housing_incharge')
def housing_dashboard(request):
    import json as _json
    total_houses     = House.objects.count()
    available_houses = House.objects.filter(status='available').count()
    occupied_houses  = House.objects.filter(status='occupied').count()
    s1_avail = House.objects.filter(site=1, status='available').count()
    s1_occ   = House.objects.filter(site=1, status='occupied').count()
    s2_avail = House.objects.filter(site=2, status='available').count()
    s2_occ   = House.objects.filter(site=2, status='occupied').count()

    pending_allocations = Application.objects.filter(
        status='approved', applicant__allocated_house__isnull=True,
    ).count()
    recent_allocations = AllocationHistory.objects.select_related(
        'house', 'beneficiary', 'allocated_by'
    ).order_by('-date')[:5]
    context = {
        'total_houses': total_houses,
        'available_houses': available_houses,
        'occupied_houses': occupied_houses,
        'pending_allocations': pending_allocations,
        's1_avail': s1_avail, 's1_occ': s1_occ,
        's2_avail': s2_avail, 's2_occ': s2_occ,
        'recent_allocations': recent_allocations,
        's1_avail_json': _json.dumps(s1_avail),
        's1_occ_json': _json.dumps(s1_occ),
        's2_avail_json': _json.dumps(s2_avail),
        's2_occ_json': _json.dumps(s2_occ),
    }
    return render(request, 'housing/dashboard_housing.html', context)


# ---------------------------------------------------------------------------
# Beneficiary Incharge Dashboard
# Note: this view intentionally does NOT query House data.
# ---------------------------------------------------------------------------
@role_required('admin', 'beneficiary_incharge')
def beneficiary_dashboard(request):
    context = {
        'total_applications': Application.objects.count(),
        'pending_applications': Application.objects.filter(status='pending').count(),
        'approved_applications': Application.objects.filter(status='approved').count(),
        'rejected_applications': Application.objects.filter(status='rejected').count(),
        'recent_applications': Application.objects.select_related(
            'applicant'
        ).order_by('-submission_date')[:5],
    }
    return render(request, 'housing/dashboard_beneficiary.html', context)


# ---------------------------------------------------------------------------
# Applicant Dashboard
# ---------------------------------------------------------------------------
@role_required('applicant')
def applicant_dashboard(request):
    application = None
    try:
        application = request.user.application
    except Application.DoesNotExist:
        pass
    allocated_house = House.objects.filter(
        allocated_to=request.user
    ).first()
    return render(request, 'housing/dashboard_applicant.html', {
        'application': application,
        'allocated_house': allocated_house,
    })


# ---------------------------------------------------------------------------
# Housed Beneficiaries Directory (Admin + all staff roles)
# ---------------------------------------------------------------------------
@login_required
def housed_list(request):
    """All individuals (HH head + members) in occupied houses."""
    if not request.user.role in ('admin', 'housing_incharge', 'beneficiary_incharge'):
        return redirect('dashboard')

    housed = (
        House.objects
        .filter(status='occupied', allocated_to__isnull=False)
        .select_related('allocated_to')
        .order_by('site', 'house_number')
    )

    # Build a flat list of individuals: HH head first, then each member
    rows = []
    for house in housed:
        try:
            app = house.allocated_to.application
        except Application.DoesNotExist:
            app = None

        # Household Head row
        rows.append({
            'house': house,
            'app': app,
            'role_label': 'Household Head',
            'fname': app.hh_fname if app else '',
            'mname': app.hh_mname if app else '',
            'lname': app.hh_lname if app else '',
            'bdate': app.hh_bdate if app else None,
            'is_head': True,
            'member': None,
        })

        # Member rows
        if app:
            for member in app.members.all():
                rows.append({
                    'house': house,
                    'app': app,
                    'role_label': member.get_relationship_display(),
                    'fname': member.fname,
                    'mname': member.mname,
                    'lname': member.lname,
                    'bdate': member.bdate,
                    'is_head': False,
                    'member': member,
                })

    return render(request, 'housing/housed_list.html', {'rows': rows})


@login_required
def beneficiary_update_name(request, pk):
    """AJAX: update household-head name fields on an Application."""
    if request.user.role not in ('admin', 'housing_incharge', 'beneficiary_incharge'):
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)

    import json
    data = json.loads(request.body)
    app = get_object_or_404(Application, pk=pk)
    app.hh_fname = data.get('fname', app.hh_fname)
    app.hh_mname = data.get('mname', app.hh_mname)
    app.hh_lname = data.get('lname', app.hh_lname)
    parts = [app.hh_lname, app.hh_fname, app.hh_mname]
    app.full_name = ', '.join(p for p in parts if p).strip(', ')
    app.save(update_fields=['hh_fname', 'hh_mname', 'hh_lname', 'full_name'])
    return JsonResponse({'ok': True, 'full_name': app.full_name})


@login_required
def member_update_name(request, pk):
    """AJAX: update a HouseholdMember's name fields."""
    if request.user.role not in ('admin', 'housing_incharge', 'beneficiary_incharge'):
        return JsonResponse({'ok': False, 'error': 'Permission denied.'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'ok': False, 'error': 'POST required.'}, status=405)

    import json
    data = json.loads(request.body)
    member = get_object_or_404(HouseholdMember, pk=pk)
    member.fname = data.get('fname', member.fname)
    member.mname = data.get('mname', member.mname)
    member.lname = data.get('lname', member.lname)
    member.save(update_fields=['fname', 'mname', 'lname'])
    return JsonResponse({'ok': True, 'full_name': f"{member.lname}, {member.fname} {member.mname}".strip(', ')})


# ---------------------------------------------------------------------------
# House List (Housing Incharge + Admin)
# ---------------------------------------------------------------------------
@role_required('admin', 'housing_incharge')
def house_list(request):
    from django.db.models import Case, When, Value, CharField
    qs = House.objects.select_related('allocated_to').annotate(
        effective_status=Case(
            When(allocated_to__isnull=True, then=Value('available')),
            default=Value('occupied'),
            output_field=CharField()
        )
    )
    site1 = qs.filter(site=1)
    site2 = qs.filter(site=2)
    return render(request, 'housing/house_list.html', {
        'site1_houses': site1,
        'site2_houses': site2,
        'site1_total': site1.count(),
        'site2_total': site2.count(),
        'site1_available': site1.filter(effective_status='available').count(),
        'site2_available': site2.filter(effective_status='available').count(),
    })



# ---------------------------------------------------------------------------
# House Detail (AJAX – returns JSON for the detail offcanvas)
# ---------------------------------------------------------------------------
@role_required('admin', 'housing_incharge')
def house_detail_json(request, pk):
    """Return house details + resident info as JSON for the detail panel."""
    house = get_object_or_404(House, pk=pk)
    
    # Effective status based on allocated_to presence
    effective_status = 'available' if house.allocated_to is None else 'occupied'

    resident = None
    members = []
    if house.allocated_to:
        u = house.allocated_to
        resident = {
            'name': u.get_full_name() or u.username,
            'username': u.username,
        }
        try:
            app = u.application
            members = list(
                app.members.values('fname', 'mname', 'lname', 'relationship', 'bdate')
            )
            for m in members:
                if m['bdate']:
                    m['bdate'] = m['bdate'].strftime('%b %d, %Y')
            resident['contact'] = app.contact_no
            resident['civil_status'] = app.get_civil_status_display()
            resident['family_size'] = app.family_size
            resident['allocation_date'] = house.allocation_date.strftime('%B %d, %Y') if house.allocation_date else None
        except Exception:
            pass

    return JsonResponse({
        'id': str(house.id),
        'house_number': house.house_number,
        'site': house.site,
        'status': house.status,
        'effective_status': effective_status,
        'status_display': house.get_status_display(),
        'svg_id': house.svg_id,
        'allocation_date': house.allocation_date.strftime('%B %d, %Y') if house.allocation_date else None,
        'resident': resident,
        'members': members,
    })



# ---------------------------------------------------------------------------
# Add House (Admin + Housing Incharge)
# ---------------------------------------------------------------------------
@role_required('admin', 'housing_incharge')
def add_house(request):
    """Manually add a single house record."""
    import re

    if request.method == 'POST':
        form = AddHouseForm(request.POST)
        if form.is_valid():
            house = form.save(commit=False)

            # Auto-generate svg_id from site + house_number
            # Expected format: "Block No. X | Lot No. Y"
            m = re.search(r'Block No\.\s*(\d+).*?Lot No\.\s*(\d+)', house.house_number, re.IGNORECASE)
            if m:
                svg_id = f's{house.site}-b{m.group(1)}-l{m.group(2)}'
            else:
                slug = re.sub(r'[^a-z0-9]', '-', house.house_number.lower())
                slug = re.sub(r'-+', '-', slug).strip('-')[:20]
                svg_id = f's{house.site}-{slug}'

            # Ensure uniqueness by appending a counter if needed
            base_id = svg_id[:28]
            svg_id = base_id
            counter = 1
            while House.objects.filter(svg_id=svg_id).exists():
                svg_id = f'{base_id}-{counter}'
                counter += 1

            house.svg_id = svg_id
            house.save()
            log_activity(request, 'add_house', f'House added: "{house.house_number}" (Site {house.site}, SVG ID: {house.svg_id}).')
            messages.success(request, f'House "{house.house_number}" added successfully.')
            return redirect('house_list')
    else:
        form = AddHouseForm()

    return render(request, 'housing/add_house.html', {'form': form})


# ---------------------------------------------------------------------------
# Import Houses from CSV (Admin + Housing Incharge)
# ---------------------------------------------------------------------------
@role_required('admin', 'housing_incharge')
def import_houses_csv(request):
    """Bulk-import houses from an uploaded CSV file."""
    import csv
    import io
    import re

    results = None  # shown after POST

    def make_svg_id(site, house_number):
        m = re.search(r'Block No\.\s*(\d+).*?Lot No\.\s*(\d+)', house_number, re.IGNORECASE)
        if m:
            return f's{site}-b{m.group(1)}-l{m.group(2)}'
        slug = re.sub(r'[^a-z0-9]', '-', house_number.lower())
        slug = re.sub(r'-+', '-', slug).strip('-')[:20]
        return f's{site}-{slug}'

    if request.method == 'POST' and request.FILES.get('csv_file'):
        csv_file = request.FILES['csv_file']

        if not csv_file.name.endswith('.csv'):
            messages.error(request, 'Please upload a valid .csv file.')
            return render(request, 'housing/import_houses.html', {'results': None})

        decoded = csv_file.read().decode('utf-8-sig')  # utf-8-sig strips BOM
        reader = csv.DictReader(io.StringIO(decoded))

        # Normalize header names (strip whitespace, lowercase)
        reader.fieldnames = [f.strip().lower() for f in (reader.fieldnames or [])]

        added = []
        skipped = []
        errors = []

        # Pre-load existing svg_ids to avoid N+1 uniqueness checks
        existing_svg_ids = set(House.objects.values_list('svg_id', flat=True))
        existing_pairs = set(
            House.objects.values_list('site', 'house_number')
        )

        for i, row in enumerate(reader, start=2):  # row 1 = header
            site_raw = row.get('site', '').strip()
            house_address = row.get('house address', row.get('house_address', '')).strip()
            coordinates = row.get('coordinates', '').strip()

            # --- Validate site ---
            if site_raw not in ('1', '2'):
                errors.append({'row': i, 'data': row, 'reason': f'Invalid site "{site_raw}". Must be 1 or 2.'})
                continue

            if not house_address:
                errors.append({'row': i, 'data': row, 'reason': 'House address is empty.'})
                continue

            site = int(site_raw)

            # --- Skip duplicate site + house_number ---
            if (site, house_address) in existing_pairs:
                skipped.append({'row': i, 'site': site, 'house_address': house_address, 'reason': 'Already exists.'})
                continue

            # --- Generate unique svg_id ---
            base_id = make_svg_id(site, house_address)[:28]
            svg_id = base_id
            counter = 1
            while svg_id in existing_svg_ids:
                svg_id = f'{base_id}-{counter}'
                counter += 1

            house = House(
                site=site,
                house_number=house_address,
                status='available',
                coordinates=coordinates,
                svg_id=svg_id,
            )
            house.save()

            existing_svg_ids.add(svg_id)
            existing_pairs.add((site, house_address))
            added.append({'row': i, 'site': site, 'house_address': house_address})

        results = {
            'added': added,
            'skipped': skipped,
            'errors': errors,
        }

        if added:
            log_activity(request, 'import_houses', f'CSV import: {len(added)} house(s) added, {len(skipped)} skipped, {len(errors)} error(s).')
            messages.success(request, f'{len(added)} house(s) imported successfully.')

    return render(request, 'housing/import_houses.html', {'results': results})


# ---------------------------------------------------------------------------
# SVG Map (Housing Incharge + Admin)
# ---------------------------------------------------------------------------
@role_required('admin', 'housing_incharge')
def map_view(request):
    """
    The interactive SVG village map – one tab per site.
    House paths are rendered server-side; the modal uses data attributes
    and calls /api/allocate/ for assignments.
    """
    site1_houses = House.objects.filter(site=1).select_related('allocated_to')
    site2_houses = House.objects.filter(site=2).select_related('allocated_to')
    return render(request, 'housing/map.html', {
        'site1_houses': site1_houses,
        'site2_houses': site2_houses,
        'can_allocate': request.user.role in ('admin', 'housing_incharge'),
    })


# ---------------------------------------------------------------------------
# Application List (Beneficiary Incharge + Housing Incharge + Admin)
# ---------------------------------------------------------------------------
@role_required('admin', 'beneficiary_incharge', 'housing_incharge')
def application_list(request):
    # Always load all apps — filtering is done client-side via DataTables
    qs = Application.objects.select_related('applicant', 'reviewed_by').all()

    allocated_applicant_ids = set(
        House.objects.filter(status='occupied', allocated_to__isnull=False)
        .values_list('allocated_to_id', flat=True)
    )

    return render(request, 'housing/application_list.html', {
        'applications': qs,
        'sending_areas': SendingArea.objects.all(),
        'allocated_applicant_ids': allocated_applicant_ids,
        'can_allocate': request.user.role in ('admin', 'housing_incharge'),
    })


# ---------------------------------------------------------------------------
# Allocate House (Housing Incharge + Admin)
# ---------------------------------------------------------------------------
@role_required('admin', 'housing_incharge')
def allocate_house(request, pk):
    """Allocate an available house to an approved applicant."""
    application = get_object_or_404(Application, pk=pk)

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if request.method != 'POST':
        return redirect('application_list')

    if application.status != 'approved':
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Only approved applications can be allocated a house.'}, status=400)
        messages.error(request, 'Only approved applications can be allocated a house.')
        return redirect('application_list')

    house_id = request.POST.get('house_id')
    if not house_id:
        if is_ajax:
            return JsonResponse({'ok': False, 'error': 'Please select a house.'}, status=400)
        messages.error(request, 'Please select a house.')
        return redirect('application_list')

    house = get_object_or_404(House, pk=house_id, status='available')

    # Check applicant doesn't already have a house
    if House.objects.filter(allocated_to=application.applicant).exists():
        if is_ajax:
            return JsonResponse({'ok': False, 'error': f'{application.full_name} already has an allocated house.'}, status=400)
        messages.warning(request, f'{application.full_name} already has an allocated house.')
        return redirect('application_list')

    house.allocated_to = application.applicant
    house.status = 'occupied'
    house.allocation_date = timezone.now().date()
    house.save()

    AllocationHistory.objects.create(
        house=house,
        beneficiary=application.applicant,
        allocated_by=request.user,
    )
    log_activity(
        request, 'allocate_house',
        f'House "{house.house_number}" (Site {house.site}) allocated to '
        f'"{application.full_name or application.applicant.username}".',
    )

    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        return JsonResponse({
            'ok': True,
            'house_number': house.house_number,
            'applicant_name': application.full_name,
            'app_id': str(application.pk),
        })

    messages.success(
        request,
        f'House "{house.house_number}" (Site {house.site}) allocated to {application.full_name}.'
    )
    return redirect('application_list')


# ---------------------------------------------------------------------------
# AJAX – Dashboard KPI stats (for Vue auto-refresh)
# ---------------------------------------------------------------------------
@role_required('admin')
def api_dashboard_stats(request):
    """JSON endpoint: live KPI counts for dashboard auto-refresh."""
    return JsonResponse({
        'total_houses': House.objects.count(),
        'available_houses': House.objects.filter(status='available').count(),
        'occupied_houses': House.objects.filter(status='occupied').count(),
        'total_applications': Application.objects.count(),
        'pending_applications': Application.objects.filter(status='pending').count(),
        'approved_applications': Application.objects.filter(status='approved').count(),
        'rejected_applications': Application.objects.filter(status='rejected').count(),
        'pending_allocations': Application.objects.filter(
            status='approved', applicant__allocated_house__isnull=True
        ).count(),
        'total_staff': CustomUser.objects.exclude(role='applicant').count(),
        'total_beneficiaries': CustomUser.objects.filter(role='applicant').count(),
    })


# ---------------------------------------------------------------------------
# AJAX – Available houses by site
# ---------------------------------------------------------------------------
@role_required('admin', 'housing_incharge')
def houses_by_site(request, site_number):
    """Return available houses for a site as JSON (used by allocation modal)."""
    from django.http import JsonResponse
    houses = House.objects.filter(
        site=site_number, status='available'
    ).order_by('house_number').values('id', 'house_number')
    return JsonResponse({'houses': list(houses)})


@role_required('admin', 'beneficiary_incharge')
def application_detail(request, pk):
    """View + review an application."""
    application = get_object_or_404(Application, pk=pk)

    # Approved/rejected applications cannot be re-reviewed
    if request.method == 'POST' and application.status in ('approved', 'rejected'):
        messages.error(request, f'This application has already been {application.status} and cannot be changed.')
        return redirect('application_detail', pk=pk)

    form = ReviewApplicationForm(request.POST or None, instance=application)
    if request.method == 'POST' and form.is_valid():
        reviewed = form.save(commit=False)
        reviewed.reviewed_by = request.user
        reviewed.review_date = timezone.now()
        reviewed.save()
        log_activity(
            request, 'review_application',
            f'Application by "{application.full_name or application.applicant.username}" '
            f'marked as {reviewed.get_status_display()}.',
        )
        messages.success(request, f'Application status updated to {reviewed.get_status_display()}.')
        return redirect('application_list')
    return render(request, 'housing/application_detail.html', {
        'application': application,
        'form': form,
    })


# ---------------------------------------------------------------------------
# Walk-in Application Entry (Admin + Beneficiary Incharge)
# ---------------------------------------------------------------------------
def _generate_username(fname, lname):
    """Generate a unique username from applicant name."""
    base = re.sub(r'[^a-z0-9]', '', (fname[:1] + lname).lower())[:10] or 'applicant'
    for _ in range(20):
        candidate = f"{base}{secrets.randbelow(9000) + 1000}"
        if not CustomUser.objects.filter(username=candidate).exists():
            return candidate
    return f"app{uuid.uuid4().hex[:8]}"


def _generate_temp_password(length=10):
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


@role_required('admin', 'beneficiary_incharge')
def walkin_application(request):
    """Staff encodes a walk-in applicant's application on their behalf."""
    form = ApplicationForm()

    if request.method == 'POST':
        form = ApplicationForm(request.POST, request.FILES)

        # Pull account fields directly from POST (not part of ApplicationForm)
        fname     = request.POST.get('walkin_fname', '').strip()
        lname     = request.POST.get('walkin_lname', '').strip()
        email     = request.POST.get('walkin_email', '').strip()
        phone     = request.POST.get('walkin_phone', '').strip()

        errors = {}
        if not fname:
            errors['walkin_fname'] = 'First name is required.'
        if not lname:
            errors['walkin_lname'] = 'Last name is required.'

        if not errors and form.is_valid():
            temp_password = _generate_temp_password()
            username      = _generate_username(fname, lname)

            # Create the applicant user account
            user = CustomUser.objects.create_user(
                username=username,
                password=temp_password,
                first_name=fname,
                last_name=lname,
                email=email,
                phone=_normalize_ph_phone(phone),
                role='applicant',
                must_change_password=True,
            )

            # Handle base64 photo/ID fields the same way my_application does
            files = request.FILES.copy()

            def inject_b64(post_key, field_name, prefix):
                data = request.POST.get(post_key, '')
                if data and data.startswith('data:image'):
                    try:
                        _, b64 = data.split(',', 1)
                        img_bytes = base64.b64decode(b64)
                        buf = BytesIO(img_bytes)
                        buf.seek(0)
                        files[field_name] = InMemoryUploadedFile(
                            buf, 'ImageField',
                            f'{prefix}_{user.pk}.jpg',
                            'image/jpeg', len(img_bytes), None,
                        )
                    except Exception:
                        pass

            inject_b64('hh_image_data',  'hh_image',         'hh')
            inject_b64('nid_front_data', 'national_id_front', 'nid_front')
            inject_b64('nid_back_data',  'national_id_back',  'nid_back')

            # Re-bind form with any injected files
            if files:
                form = ApplicationForm(request.POST, files)
                form.is_valid()

            app = form.save(commit=False)
            app.applicant  = user
            app.is_walkin  = True
            app.entered_by = request.user
            app.family_size = 1  # Will be updated below after members are saved
            app.save()

            # Save household members
            member_count = int(request.POST.get('member_count', 0))
            for i in range(member_count):
                m_fname = request.POST.get(f'member_fname_{i}', '').strip()
                m_lname = request.POST.get(f'member_lname_{i}', '').strip()
                if m_fname and m_lname:
                    try:
                        member_bdate = _parse_member_bdate(request.POST.get(f'member_bdate_{i}', ''))
                    except ValueError:
                        member_bdate = None
                    HouseholdMember.objects.create(
                        application=app,
                        fname=m_fname,
                        mname=request.POST.get(f'member_mname_{i}', '').strip(),
                        lname=m_lname,
                        relationship=request.POST.get(f'member_relationship_{i}', 'other_relative'),
                        bdate=member_bdate,
                    )

            # Update family_size = head + members
            app.family_size = 1 + app.members.count()
            app.save(update_fields=['family_size'])

            log_activity(
                request, 'walkin_entry',
                f'Walk-in application entered for "{fname} {lname}" '
                f'(username: {username}).',
            )

            return render(request, 'housing/walkin_application.html', {
                'success': True,
                'credentials': {
                    'username': username,
                    'password': temp_password,
                    'full_name': f'{fname} {lname}',
                },
            })

        return render(request, 'housing/walkin_application.html', {
            'form': form,
            'walkin_errors': errors,
            'post': request.POST,
        })

    return render(request, 'housing/walkin_application.html', {'form': form})


# ---------------------------------------------------------------------------
# My Application (Applicant only)
# ---------------------------------------------------------------------------
@role_required('applicant')
def my_application(request):
    """Create or edit the applicant's own application."""
    try:
        application = request.user.application
        can_edit = application.status == 'pending'
    except Application.DoesNotExist:
        application = None
        can_edit = True

    if request.method == 'POST' and can_edit:
        # Convert base64 camera captures into uploaded files
        files = request.FILES.copy()

        def inject_b64(post_key, field_name, prefix):
            data = request.POST.get(post_key, '')
            if data and data.startswith('data:image'):
                try:
                    _, b64 = data.split(',', 1)
                    img_bytes = base64.b64decode(b64)
                    files[field_name] = InMemoryUploadedFile(
                        BytesIO(img_bytes), field_name,
                        f"{prefix}_{uuid.uuid4().hex}.jpg",
                        'image/jpeg', len(img_bytes), None,
                    )
                except Exception:
                    pass

        inject_b64('hh_image_data',  'hh_image',          'hh')
        inject_b64('nid_front_data', 'national_id_front', 'nid_front')
        inject_b64('nid_back_data',  'national_id_back',  'nid_back')

        if application:
            form = ApplicationForm(request.POST, files, instance=application)
        else:
            form = ApplicationForm(request.POST, files)

        if form.is_valid():
            saved = form.save(commit=False)
            saved.applicant = request.user
            saved.save()

            # Save household members (clear old, insert new)
            saved.members.all().delete()
            member_count = int(request.POST.get('member_count', 0))
            for i in range(member_count):
                fname = request.POST.get(f'member_fname_{i}', '').strip()
                lname = request.POST.get(f'member_lname_{i}', '').strip()
                if fname or lname:
                    try:
                        member_bdate = _parse_member_bdate(request.POST.get(f'member_bdate_{i}', ''))
                    except ValueError:
                        member_bdate = None
                    HouseholdMember.objects.create(
                        application=saved,
                        fname=fname,
                        mname=request.POST.get(f'member_mname_{i}', '').strip(),
                        lname=lname,
                        relationship=request.POST.get(f'member_relationship_{i}', 'other_relative'),
                        bdate=member_bdate,
                    )

            # Auto-calculate family size: household head (1) + members
            saved.family_size = saved.members.count() + 1
            saved.save(update_fields=['family_size'])

            messages.success(request, 'Your application has been saved.')
            return redirect('my_application')
    else:
        form = ApplicationForm(instance=application)

    existing_members = list(application.members.all()) if application else []

    return render(request, 'housing/my_application.html', {
        'form': form,
        'application': application,
        'can_edit': can_edit,
        'existing_members': existing_members,
    })


# ---------------------------------------------------------------------------
# Household Member Search (Applicant — AJAX)
# ---------------------------------------------------------------------------
@login_required
def member_search(request):
    """Search for a person by first name, last name, and birthdate across household members."""
    fname = request.GET.get('fname', '').strip()
    lname = request.GET.get('lname', '').strip()
    bdate = request.GET.get('bdate', '').strip()  # YYYY-MM-DD
    results = []

    if fname and lname and bdate:
        member_qs = HouseholdMember.objects.filter(
            fname__icontains=fname,
            lname__icontains=lname,
            bdate=bdate,
        )

        # Search existing household members
        members = member_qs.select_related('application', 'application__applicant')[:8]

        seen = set()
        for m in members:
            key = f"{m.lname}_{m.fname}_{m.bdate}"
            if key in seen:
                continue
            seen.add(key)
            app = m.application
            house = House.objects.filter(allocated_to=app.applicant).first()
            results.append({
                'name': f"{m.lname}, {m.fname} {m.mname}".strip(', '),
                'type': 'member',
                'in': app.full_name or app.applicant.username,
                'housed': bool(house),
                'house': house.house_number if house else None,
            })

        # Also check household heads with same name + bdate
        apps = Application.objects.filter(
            hh_fname__icontains=fname,
            hh_lname__icontains=lname,
            hh_bdate=bdate,
        ).select_related('applicant')[:5]

        for app in apps:
            name = f"{app.hh_lname}, {app.hh_fname} {app.hh_mname}".strip(', ')
            key = f"{app.hh_lname}_{app.hh_fname}"
            if key in seen or not (app.hh_fname or app.hh_lname):
                continue
            seen.add(key)
            house = House.objects.filter(allocated_to=app.applicant).first()
            results.append({
                'name': name or app.full_name,
                'type': 'head',
                'in': app.applicant.username,
                'housed': bool(house),
                'house': house.house_number if house else None,
            })

    return JsonResponse({'results': results})


# ---------------------------------------------------------------------------
# User Management (Admin only)
# ---------------------------------------------------------------------------
@role_required('admin')
def user_management(request):
    users = CustomUser.objects.all().order_by('role', 'date_joined')
    return render(request, 'housing/user_management.html', {'users': users})


@role_required('admin')
def toggle_user_active(request, pk):
    """Admin can activate/deactivate users (AJAX)."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    user = get_object_or_404(CustomUser, pk=pk)
    if user == request.user:
        return JsonResponse({'ok': False, 'error': 'You cannot deactivate your own account.'})
    user.is_active = not user.is_active
    user.save()
    state = 'activated' if user.is_active else 'deactivated'
    log_activity(request, 'toggle_user', f'User "{user.username}" {state}.')
    return JsonResponse({'ok': True, 'is_active': user.is_active})


@role_required('admin')
def create_staff_user(request):
    """Admin creates a housing_incharge or beneficiary_incharge account."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    import json, secrets, string
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid request data.'}, status=400)

    ALLOWED_ROLES = ('admin', 'housing_incharge', 'beneficiary_incharge')
    role = data.get('role', '')
    if role not in ALLOWED_ROLES:
        return JsonResponse({'ok': False, 'error': 'Invalid role.'})

    username = data.get('username', '').strip()
    if not username:
        return JsonResponse({'ok': False, 'error': 'Username is required.'})
    if CustomUser.objects.filter(username=username).exists():
        return JsonResponse({'ok': False, 'error': 'Username already taken.'})

    # Auto-generate a readable temporary password
    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(12))

    user = CustomUser(
        username=username,
        first_name=data.get('first_name', '').strip(),
        last_name=data.get('last_name', '').strip(),
        email=data.get('email', '').strip(),
        phone=_normalize_ph_phone(data.get('phone', '').strip()),
        role=role,
        is_active=True,
        must_change_password=True,
    )
    user.set_password(temp_password)
    user.save()
    log_activity(
        request, 'create_user',
        f'Staff user created: "{user.username}" ({user.get_role_display()}).',
    )

    return JsonResponse({
        'ok': True,
        'temp_password': temp_password,
        'user': {
            'pk': user.pk,
            'username': user.username,
            'full_name': user.get_full_name() or '—',
            'email': user.email or '—',
            'role': user.role,
            'role_display': user.get_role_display(),
            'phone': user.phone or '—',
            'is_active': True,
            'date_joined': user.date_joined.strftime('%b %d, %Y'),
        }
    })


@role_required('admin')
def update_user(request, pk):
    """Admin edits a user's details and/or role."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    import json
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'ok': False, 'error': 'Invalid request data.'}, status=400)

    user = get_object_or_404(CustomUser, pk=pk)

    ALLOWED_ROLES = ('admin', 'housing_incharge', 'beneficiary_incharge', 'applicant')
    role = data.get('role', user.role)
    if role not in ALLOWED_ROLES:
        return JsonResponse({'ok': False, 'error': 'Invalid role.'})

    new_username = data.get('username', user.username).strip()
    if not new_username:
        return JsonResponse({'ok': False, 'error': 'Username is required.'})
    if CustomUser.objects.exclude(pk=pk).filter(username=new_username).exists():
        return JsonResponse({'ok': False, 'error': 'Username already taken.'})

    user.username   = new_username
    user.first_name = data.get('first_name', user.first_name).strip()
    user.last_name  = data.get('last_name', user.last_name).strip()
    user.email      = data.get('email', user.email).strip()
    user.phone      = _normalize_ph_phone(data.get('phone', user.phone).strip())
    user.role       = role

    password = data.get('password', '').strip()
    if password:
        if len(password) < 6:
            return JsonResponse({'ok': False, 'error': 'Password must be at least 6 characters.'})
        if password != data.get('password2', '').strip():
            return JsonResponse({'ok': False, 'error': 'Passwords do not match.'})
        user.set_password(password)

    user.save()
    log_activity(request, 'update_user', f'User "{user.username}" updated by admin.')
    return JsonResponse({
        'ok': True,
        'user': {
            'pk': user.pk,
            'username': user.username,
            'full_name': user.get_full_name() or '—',
            'email': user.email or '—',
            'role': user.role,
            'role_display': user.get_role_display(),
            'phone': user.phone or '—',
            'is_active': user.is_active,
        }
    })


@role_required('admin')
def delete_user(request, pk):
    """Admin deletes a user (cannot delete self)."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    user = get_object_or_404(CustomUser, pk=pk)
    if user == request.user:
        return JsonResponse({'ok': False, 'error': 'You cannot delete your own account.'})
    username_snapshot = user.username
    role_snapshot = user.get_role_display()
    user.delete()
    log_activity(request, 'delete_user', f'User "{username_snapshot}" ({role_snapshot}) deleted.')
    return JsonResponse({'ok': True})


# ---------------------------------------------------------------------------
# Activity Log (Admin only)
# ---------------------------------------------------------------------------
@role_required('admin')
def activity_log_view(request):
    """Display the full activity log. Admin eyes only."""
    logs = ActivityLog.objects.select_related('user').order_by('-timestamp')

    # Optional filters
    action_filter = request.GET.get('action', '').strip()
    user_filter   = request.GET.get('user', '').strip()

    if action_filter:
        logs = logs.filter(action=action_filter)
    if user_filter:
        logs = logs.filter(user__username__icontains=user_filter)

    return render(request, 'housing/activity_log.html', {
        'logs': logs,
        'action_choices': ActivityLog.ACTION_CHOICES,
        'action_filter': action_filter,
        'user_filter': user_filter,
    })
