from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now

from accounts.models import UserModule
from registration.models import Student
from audit.services import log_action

from .models import HealthVisit


def has_health_access(user):
    if user.is_superuser:
        return True
    return UserModule.objects.filter(user=user, module__name='health', is_approved=True).exists()


@login_required
def health_dashboard(request):
    if not has_health_access(request.user):
        messages.error(request, "Access denied. You do not have access to the Health module.")
        return redirect('dashboard')

    total_visits = HealthVisit.objects.count()
    visits_today = HealthVisit.objects.filter(visit_date__date=now().date()).count()
    referred_count = HealthVisit.objects.filter(referred_to_hospital=True).count()
    pending_followups = HealthVisit.objects.filter(follow_up_required=True, follow_up_date__gte=now().date()).count()

    recent_visits = HealthVisit.objects.select_related('student').order_by('-visit_date')[:8]

    return render(request, 'health/dashboard.html', {
        'total_visits': total_visits,
        'visits_today': visits_today,
        'referred_count': referred_count,
        'pending_followups': pending_followups,
        'recent_visits': recent_visits,
    })


@login_required
def visit_list(request):
    if not has_health_access(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    query = request.GET.get('q', '').strip()
    visits = HealthVisit.objects.select_related('student').order_by('-visit_date')

    if query:
        visits = visits.filter(
            Q(student__first_name__icontains=query) |
            Q(student__last_name__icontains=query) |
            Q(student__registration_number__icontains=query) |
            Q(reason__icontains=query)
        )

    paginator = Paginator(visits, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'health/visit_list.html', {'page_obj': page_obj, 'query': query})


@login_required
def add_visit(request, student_id=None):
    if not has_health_access(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    student = None
    if student_id:
        student = get_object_or_404(Student, id=student_id)

    if request.method == 'POST':
        student = get_object_or_404(Student, id=request.POST.get('student_id'))
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, "Reason for visit is required.")
            return redirect('health:add_visit')

        follow_up_required = request.POST.get('follow_up_required') == 'on'

        visit = HealthVisit.objects.create(
            student=student,
            reason=reason,
            symptoms=request.POST.get('symptoms', '').strip(),
            treatment_given=request.POST.get('treatment_given', '').strip(),
            referred_to_hospital=request.POST.get('referred_to_hospital') == 'on',
            follow_up_required=follow_up_required,
            follow_up_date=request.POST.get('follow_up_date') or None,
            recorded_by=request.user,
            notes=request.POST.get('notes', '').strip(),
        )

        log_action(
            user=request.user, action='create', instance=visit, module='health',
            changes={'student': str(student), 'reason': visit.reason}
        )

        messages.success(request, f"Health visit recorded for {student}.")
        return redirect('health:student_history', student_id=student.id)

    students = Student.objects.filter(is_archived=False).order_by('first_name')
    return render(request, 'health/add_visit.html', {'students': students, 'selected_student': student})


@login_required
def student_history(request, student_id):
    if not has_health_access(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    student = get_object_or_404(Student, id=student_id)
    visits = HealthVisit.objects.filter(student=student).order_by('-visit_date')

    return render(request, 'health/student_history.html', {'student': student, 'visits': visits})
