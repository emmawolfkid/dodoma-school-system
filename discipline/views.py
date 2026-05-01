from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count, Q
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST
from django.http import HttpResponse

from .models import DisciplineCase, DisciplineAuditLog, SuspensionRecord
from .forms import DisciplineCaseForm, SuspensionForm   # ✅ FIXED
from .decorators import discipline_permission_required
from django.utils.timezone import now
from registration.models import Student

# ✅ OPTIONAL SAFE IMPORT (prevents crash if reportlab missing)
try:
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


# 🔥 DASHBOARD
@discipline_permission_required('view')
def discipline_dashboard(request):

    stats = DisciplineCase.objects.filter(is_archived=False).aggregate(
        total=Count('id'),
        major=Count('id', filter=Q(case_type='major')),
        minor=Count('id', filter=Q(case_type='minor')),
        open=Count('id', filter=Q(status='open')),
        resolved=Count('id', filter=Q(status='resolved')),
        severity_total=Sum('severity_points')
    )

    recent_cases = DisciplineCase.objects.filter(
        is_archived=False
    ).select_related('student').order_by('-date_reported')[:5]

    active_suspensions = SuspensionRecord.objects.filter(status='active').count()

    return render(request, 'discipline/dashboard.html', {
        'total_cases': stats['total'],
        'major_cases': stats['major'],
        'minor_cases': stats['minor'],
        'open_cases': stats['open'],
        'resolved_cases': stats['resolved'],
        'severity_total': stats['severity_total'] or 0,
        'recent_cases': recent_cases,
        'active_suspensions': active_suspensions
    })


# 🔥 STUDENT PROFILE
@discipline_permission_required('view')
def student_discipline_profile(request, student_id):

    student = get_object_or_404(Student, id=student_id)

    cases = student.discipline_cases.filter(
        is_archived=False
    ).select_related('reported_by', 'suspension').order_by('-date_reported')

    logs = DisciplineAuditLog.objects.filter(
        case__student=student
    ).select_related('performed_by', 'case')[:20]

    return render(request, 'discipline/student_profile.html', {
        'student': student,
        'cases': cases,
        'logs': logs
    })


# 🔥 ADD CASE + SUSPENSION
from django.contrib import messages
@discipline_permission_required('add')
def add_case(request, student_id):

    student = get_object_or_404(Student, id=student_id)

    if request.method == 'POST':
        form = DisciplineCaseForm(request.POST)
        suspension_form = SuspensionForm(request.POST)

        if form.is_valid():
            action_taken = form.cleaned_data.get('action_taken')
            
            # Create the case
            case = form.save(commit=False)
            case.student = student
            case.reported_by = request.user
            case.action_type = action_taken  # Map to model's action_type
            case.action_taken = action_taken.capitalize()  # Store the action description
            case.save()

            # 🔥 HANDLE SUSPENSION - only if action is suspension
            if action_taken == 'suspension':
                # Validate suspension fields before saving
                if suspension_form.validate_for_suspension():
                    suspension = suspension_form.save(commit=False)
                    suspension.case = case
                    suspension.save()
                else:
                    # Delete the case we just created since suspension failed
                    case.delete()
                    messages.error(request, "Suspension details are required and must be valid.")
                    return render(request, 'discipline/add_case.html', {
                        'form': form,
                        'suspension_form': suspension_form,
                        'student': student
                    })

            student.update_school_status()
            messages.success(request, "Case added successfully.")
            return redirect('discipline:student_profile', student_id=student.id)

        else:
            messages.error(request, "Please fix the errors below.")

    else:
        form = DisciplineCaseForm()
        suspension_form = SuspensionForm()

    return render(request, 'discipline/add_case.html', {
        'form': form,
        'suspension_form': suspension_form,
        'student': student
    })

# 🔥 ALL CASES
@discipline_permission_required('view')
def all_cases(request):

    cases = DisciplineCase.objects.filter(
        is_archived=False
    ).select_related('student', 'reported_by', 'suspension')

    status = request.GET.get('status')
    case_type = request.GET.get('type')
    search = request.GET.get('search')

    if status:
        cases = cases.filter(status=status)

    if case_type:
        cases = cases.filter(case_type=case_type)

    if search:
        cases = cases.filter(
            Q(student__first_name__icontains=search) |
            Q(student__last_name__icontains=search) |
            Q(student__registration_number__icontains=search)
        )

    cases = cases.order_by('-date_reported', '-id')

    paginator = Paginator(cases, 10)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'discipline/all_cases.html', {
        'page_obj': page_obj
    })


# 🔥 RESOLVE
@require_POST
@discipline_permission_required('edit')
def resolve_case(request, case_id):

    case = get_object_or_404(DisciplineCase, id=case_id)

    case.status = 'resolved'
    case.save()

    DisciplineAuditLog.objects.create(
        case=case,
        action='resolved',
        performed_by=request.user
    )

    case.student.update_school_status()

    return redirect('discipline:all_cases')


# 🔥 EDIT
from django.contrib import messages

@discipline_permission_required('edit')
def edit_case(request, case_id):

    case = get_object_or_404(DisciplineCase, id=case_id)
    
    # ✅ Get existing suspension (if any)
    suspension = getattr(case, 'suspension', None)

    if request.method == 'POST':
        form = DisciplineCaseForm(request.POST, instance=case)
        suspension_form = SuspensionForm(request.POST, instance=suspension)

        if form.is_valid():
            action_taken = form.cleaned_data.get('action_taken')
            
            # Update case fields
            case = form.save(commit=False)
            case.action_type = action_taken
            case.action_taken = action_taken.capitalize()
            case.save()

            # 🔥 HANDLE SUSPENSION
            if action_taken == 'suspension':
                # Validate suspension is complete
                if suspension_form.validate_for_suspension():
                    suspension = suspension_form.save(commit=False)
                    suspension.case = case
                    suspension.save()
                else:
                    messages.error(request, "Suspension details are required and must be valid.")
                    return render(request, 'discipline/add_case.html', {
                        'form': form,
                        'suspension_form': suspension_form,
                        'student': case.student,
                        'is_edit': True
                    })
            else:
                # ❗ If not suspension → delete existing suspension
                if suspension:
                    suspension.delete()

            # 🔥 LOG
            DisciplineAuditLog.objects.create(
                case=case,
                action='updated',
                performed_by=request.user
            )

            case.student.update_school_status()
            messages.success(request, "Case updated successfully.")
            return redirect('discipline:student_profile', student_id=case.student.id)

        else:
            messages.error(request, "Please fix the errors below.")

    else:
        # Pre-populate form with existing data
        form = DisciplineCaseForm(instance=case)
        # Set initial action_taken from case
        form.fields['action_taken'].initial = case.action_type
        
        suspension_form = SuspensionForm(instance=suspension)

    return render(request, 'discipline/add_case.html', {
        'form': form,
        'suspension_form': suspension_form,
        'student': case.student,
        'is_edit': True
    })

# 🔥 ARCHIVE
@require_POST
@discipline_permission_required('delete')
def archive_case(request, case_id):

    case = get_object_or_404(DisciplineCase, id=case_id)

    case.is_archived = True
    case.save()

    DisciplineAuditLog.objects.create(
        case=case,
        action='archived',
        performed_by=request.user
    )

    return redirect('discipline:all_cases')
@require_POST
@discipline_permission_required('edit')
def restore_case(request, case_id):

    case = get_object_or_404(DisciplineCase, id=case_id)

    case.is_archived = False
    case.save()

    DisciplineAuditLog.objects.create(
        case=case,
        action='restored',
        performed_by=request.user
    )

    messages.success(request, "Case restored successfully.")

    return redirect('discipline:all_cases')

# 🔥 PDF (SAFE)
@discipline_permission_required('view')
def student_report(request, student_id):

    if not REPORTLAB_AVAILABLE:
        return HttpResponse("PDF generation not available", status=500)

    student = get_object_or_404(Student, id=student_id)

    cases = student.discipline_cases.filter(is_archived=False)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'{student.registration_number}_report.pdf'

    doc = SimpleDocTemplate(response)
    styles = getSampleStyleSheet()

    content = [Paragraph(f"Student: {student}", styles['Title']), Spacer(1, 10)]

    for case in cases:
        content.append(Paragraph(f"{case.title} ({case.status})", styles['Normal']))
        content.append(Spacer(1, 5))

    doc.build(content)

    return response

@discipline_permission_required('view')
def class_list(request):
    from registration.models import Student

    classes = Student.objects.filter(
        is_archived=False
    ).values_list('student_class', flat=True).distinct().order_by('student_class')

    return render(request, 'discipline/class_list.html', {
        'classes': classes
    })


@discipline_permission_required('view')
def students_by_class(request, class_name):
    from registration.models import Student

    students = Student.objects.filter(
        student_class=class_name,
        is_archived=False
    )

    return render(request, 'discipline/students_by_class.html', {
        'students': students,
        'class_name': class_name
    })
# 🔥 ALL CASES PDF (RESTORED - DO NOT REMOVE AGAIN)
@discipline_permission_required('view')
def all_cases_report(request):

    show_archived = request.GET.get('archived')

    if show_archived:
        cases = DisciplineCase.objects.filter(is_archived=True)
    else:
        cases = DisciplineCase.objects.filter(is_archived=False)

    status = request.GET.get('status')
    case_type = request.GET.get('type')

    if status:
        cases = cases.filter(status=status)

    if case_type:
        cases = cases.filter(case_type=case_type)

    cases = cases.select_related('student').order_by('-date_reported')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="all_cases_report.pdf"'

    doc = SimpleDocTemplate(response)
    styles = getSampleStyleSheet()

    content = []

    content.append(Paragraph("Discipline Report", styles['Title']))
    content.append(Spacer(1, 10))

    for case in cases:
        text = f"{case.student} | {case.title} | {case.get_status_display()}"
        content.append(Paragraph(text, styles['Normal']))
        content.append(Spacer(1, 5))

    doc.build(content)

    return response

@require_POST
@discipline_permission_required('edit')
def mark_returned(request, case_id):

    case = get_object_or_404(DisciplineCase, id=case_id)

    if hasattr(case, 'suspension'):
        suspension = case.suspension
        suspension.actual_return_date = now().date()
        suspension.save()

        messages.success(request, "Student marked as returned.")

    return redirect('discipline:student_profile', student_id=case.student.id)