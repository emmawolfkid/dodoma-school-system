from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render, redirect

from registration.models import Student
from academic.models import Exam, Result
from discipline.models import DisciplineCase
from library.models import Book, BorrowRecord
from health.models import HealthVisit


def has_analytics_access(user):
    # Analytics surfaces data from every module, including discipline and
    # health records -- keep it to superusers rather than adding yet
    # another per-module approval flow for a read-only overview page.
    return user.is_superuser


@login_required
def analytics_dashboard(request):
    if not has_analytics_access(request.user):
        messages.error(request, "Access denied. Analytics is for system admins only.")
        return redirect('dashboard')

    # --- Enrollment ---
    active_students = Student.objects.filter(is_archived=False, school_status='Active')
    total_active = active_students.count()

    class_counts = list(
        active_students.values('student_class')
        .annotate(count=Count('id'))
        .order_by('student_class')
    )
    max_class_count = max((c['count'] for c in class_counts), default=1)

    gender_counts = list(active_students.values('gender').annotate(count=Count('id')))

    # --- Academic performance (most recently published exam) ---
    latest_exam = Exam.objects.filter(is_published=True).order_by('-created_at').first()
    division_breakdown = []
    exam_pass_rate = None
    if latest_exam:
        results = Result.objects.filter(exam=latest_exam)
        total_results = results.count()
        division_breakdown = list(
            results.values('division').annotate(count=Count('id')).order_by('division')
        )
        max_division_count = max((d['count'] for d in division_breakdown), default=1)
        passing = results.exclude(division__in=['Division 0', 'Incomplete']).count()
        exam_pass_rate = round((passing / total_results) * 100, 1) if total_results else 0
    else:
        max_division_count = 1

    # --- Discipline ---
    open_cases = DisciplineCase.objects.filter(is_archived=False, status='open').count()
    resolved_cases = DisciplineCase.objects.filter(is_archived=False, status='resolved').count()
    case_type_counts = list(
        DisciplineCase.objects.filter(is_archived=False).values('case_type').annotate(count=Count('id'))
    )

    # --- Library & Health quick stats ---
    total_books = Book.objects.count()
    borrowed_out = BorrowRecord.objects.filter(status='borrowed').count()
    total_health_visits = HealthVisit.objects.count()
    referred_count = HealthVisit.objects.filter(referred_to_hospital=True).count()

    return render(request, 'analytics/dashboard.html', {
        'total_active': total_active,
        'class_counts': class_counts,
        'max_class_count': max_class_count,
        'gender_counts': gender_counts,

        'latest_exam': latest_exam,
        'division_breakdown': division_breakdown,
        'max_division_count': max_division_count,
        'exam_pass_rate': exam_pass_rate,

        'open_cases': open_cases,
        'resolved_cases': resolved_cases,
        'case_type_counts': case_type_counts,

        'total_books': total_books,
        'borrowed_out': borrowed_out,
        'total_health_visits': total_health_visits,
        'referred_count': referred_count,
    })
