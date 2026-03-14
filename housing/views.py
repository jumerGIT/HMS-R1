"""
Template-based views for the Housing Management System.
Role checks are enforced with decorators and explicit redirects.
"""
import base64
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

from .forms import AddHouseForm, ApplicationForm, RegisterForm, ReviewApplicationForm
from .models import AllocationHistory, Application, CustomUser, House, HouseholdMember, SendingArea


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
        login(request, form.get_user())
        return redirect('dashboard')
    return render(request, 'housing/login.html', {'form': form})


def logout_view(request):
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
                messages.success(request, 'Password updated successfully.')
                return redirect('dashboard')
    return render(request, 'housing/change_password.html', {'error': error, 'forced': forced})


# ---------------------------------------------------------------------------
# Admin Dashboard
# ---------------------------------------------------------------------------
@role_required('admin')
def admin_dashboard(request):
    import json as _json
    from datetime import date, timedelta
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

    six_months_ago = date.today().replace(day=1) - timedelta(days=150)
    monthly_qs = (
        AllocationHistory.objects
        .filter(date__gte=six_months_ago)
        .annotate(month=TruncMonth('date'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    monthly_labels = [row['month'].strftime('%b %Y') for row in monthly_qs]
    monthly_data   = [row['count'] for row in monthly_qs]

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
        ).order_by('-date')[:8],
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
    qs = House.objects.select_related('allocated_to').all()
    site1 = qs.filter(site=1)
    site2 = qs.filter(site=2)
    return render(request, 'housing/house_list.html', {
        'site1_houses': site1,
        'site2_houses': site2,
        'site1_total': site1.count(),
        'site2_total': site2.count(),
        'site1_available': site1.filter(status='available').count(),
        'site2_available': site2.filter(status='available').count(),
    })


# ---------------------------------------------------------------------------
# House Detail (AJAX – returns JSON for the detail offcanvas)
# ---------------------------------------------------------------------------
@role_required('admin', 'housing_incharge')
def house_detail_json(request, pk):
    """Return house details + resident info as JSON for the detail panel."""
    house = get_object_or_404(House, pk=pk)

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
    status_filter = request.GET.get('status', '')
    qs = Application.objects.select_related('applicant', 'reviewed_by').all()
    if status_filter in ('pending', 'approved', 'rejected'):
        qs = qs.filter(status=status_filter)

    # Pre-fetch allocated houses so we can show "already allocated" state
    allocated_applicant_ids = set(
        House.objects.filter(status='occupied', allocated_to__isnull=False)
        .values_list('allocated_to_id', flat=True)
    )

    return render(request, 'housing/application_list.html', {
        'applications': qs,
        'status_filter': status_filter,
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

    if request.method != 'POST':
        return redirect('application_list')

    if application.status != 'approved':
        messages.error(request, 'Only approved applications can be allocated a house.')
        return redirect('application_list')

    house_id = request.POST.get('house_id')
    if not house_id:
        messages.error(request, 'Please select a house.')
        return redirect('application_list')

    house = get_object_or_404(House, pk=house_id, status='available')

    # Check applicant doesn't already have a house
    if House.objects.filter(allocated_to=application.applicant).exists():
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

    messages.success(
        request,
        f'House "{house.house_number}" (Site {house.site}) allocated to {application.full_name}.'
    )
    return redirect('application_list')


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
    form = ReviewApplicationForm(request.POST or None, instance=application)
    if request.method == 'POST' and form.is_valid():
        reviewed = form.save(commit=False)
        reviewed.reviewed_by = request.user
        reviewed.review_date = timezone.now()
        reviewed.save()
        messages.success(request, f'Application status updated to {reviewed.get_status_display()}.')
        return redirect('application_list')
    return render(request, 'housing/application_detail.html', {
        'application': application,
        'form': form,
    })


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
                    HouseholdMember.objects.create(
                        application=saved,
                        fname=fname,
                        mname=request.POST.get(f'member_mname_{i}', '').strip(),
                        lname=lname,
                        relationship=request.POST.get(f'member_relationship_{i}', 'other_relative'),
                        bdate=request.POST.get(f'member_bdate_{i}') or None,
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
    return JsonResponse({'ok': True, 'is_active': user.is_active})


@role_required('admin')
def create_staff_user(request):
    """Admin creates a housing_incharge or beneficiary_incharge account."""
    if request.method != 'POST':
        return JsonResponse({'ok': False}, status=405)
    import json, secrets, string
    data = json.loads(request.body)

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
        phone=data.get('phone', '').strip(),
        role=role,
        is_active=True,
        must_change_password=True,
    )
    user.set_password(temp_password)
    user.save()

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
    data = json.loads(request.body)

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
    user.phone      = data.get('phone', user.phone).strip()
    user.role       = role

    password = data.get('password', '').strip()
    if password:
        if len(password) < 6:
            return JsonResponse({'ok': False, 'error': 'Password must be at least 6 characters.'})
        if password != data.get('password2', '').strip():
            return JsonResponse({'ok': False, 'error': 'Passwords do not match.'})
        user.set_password(password)

    user.save()
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
    user.delete()
    return JsonResponse({'ok': True})
