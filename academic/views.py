from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Count
from django.http import HttpResponse

import openpyxl

from accounts.models import User, UserModule
from registration.models import Student
from .models import TeacherSubject, Exam, StudentMark, Subject, AcademicYear, Result, Paper, TeacherSubjectRequest, Notification, Combination, MarkSubmission
from .utils import calculate_student_result, rank_students, get_olevel_grade, get_alevel_grade
from .utils_notifications import create_notification, notify_many, notify_module_admins
from .pdf_utils import generate_student_pdf, generate_class_pdf
from audit.services import log_action  # ðŸ”¥ STEP 1 â€” IMPORT ADDED


ACADEMIC_CLASSES = ["Form 1", "Form 2", "Form 3", "Form 4", "Form 5", "Form 6"]
from django.db.models import Q
from accounts.models import UserModule

def can_manage_results(user):

    if user.is_superuser:
        return True

    return UserModule.objects.filter(
        user=user,
        module__name='academic',
        is_approved=True
    ).filter(
        Q(is_admin=True) | Q(is_exam_coordinator=True)
    ).exists()

def get_class_level(student_class):
    if student_class in ["Form 1", "Form 2", "Form 3", "Form 4"]:
        return 'O'
    if student_class in ["Form 5", "Form 6"]:
        return 'A'
    return None


def get_students_for_exam(exam):
    students = Student.objects.filter(
        school_status='Active',
        is_archived=False
    )

    if exam.student_class in ACADEMIC_CLASSES:
        return students.filter(student_class=exam.student_class)
    if exam.student_class == 'all_olevel':
        return students.filter(student_class__in=["Form 1", "Form 2", "Form 3", "Form 4"])
    if exam.student_class == 'all_alevel':
        return students.filter(student_class__in=["Form 5", "Form 6"])
    return students


def is_academic_admin(user):
    if user.is_superuser:
        return True

    return UserModule.objects.filter(
        user=user,
        module__name='academic',
        is_approved=True,
        is_admin=True
    ).exists()


def get_students_for_subject_class(subject, student_class):
    students = Student.objects.filter(
        student_class__iexact=student_class.strip(),
        school_status='Active',
        is_archived=False
    )

    if get_class_level(student_class) == 'A':
        subject_code = subject.code.upper().strip() if subject.code else ""

        if subject_code.startswith("GS"):
            return students

        combos = Combination.objects.filter(subjects=subject)
        combo_names = [combo.name.strip().upper() for combo in combos]

        if not combo_names:
            return Student.objects.none()

        students = students.filter(section__in=combo_names).distinct()

    return students.order_by('first_name', 'last_name')


def parse_excel_mark(value):
    if value is None:
        return None, False, None

    if isinstance(value, str):
        cleaned = value.strip().upper()
        if not cleaned:
            return None, False, None
        if cleaned in ["ABS", "A", "ABSENT"]:
            return 0, True, None
        value = cleaned

    try:
        mark = float(value)
    except (TypeError, ValueError):
        return None, False, "not a valid number"

    return mark, False, None


# ===============================
# ACADEMIC DASHBOARD
# ===============================
@login_required
def academic_dashboard(request):
    user = request.user
    
    # ðŸ”¥ SUPERUSER
    if user.is_superuser:
        role = 'admin'
        # Add stats for admin
        total_exams = Exam.objects.count()
        total_teachers = User.objects.filter(
            usermodule__module__name='academic',
            usermodule__is_approved=True
        ).count()
        published_exams = Exam.objects.filter(is_published=True).count()
    else:
        user_module = UserModule.objects.filter(
            user=user,
            module__name='academic',
            is_approved=True
        ).first()
        
        if not user_module:
            messages.error(request, "Access denied.")
            return redirect('dashboard')
        
        # ðŸ”¥ ROLE DETECTION
        if user_module.is_admin:
            role = 'academic_admin'
            # Add stats for academic admin
            total_exams = Exam.objects.count()
            total_teachers = User.objects.filter(
                usermodule__module__name='academic',
                usermodule__is_approved=True
            ).count()
            published_exams = Exam.objects.filter(is_published=True).count()
        elif user_module.is_exam_coordinator:
            role = 'exam_coordinator'
            total_exams = Exam.objects.count()
            published_exams = Exam.objects.filter(is_published=True).count()
        else:
            role = 'teacher'
            # Add stats for teacher
            assigned_subjects_count = TeacherSubject.objects.filter(
                teacher=request.user,
                is_active=True
            ).count()
    
    # ðŸ”” NOTIFICATIONS
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    # ðŸ“‹ REQUEST COUNT
    pending_requests = TeacherSubjectRequest.objects.filter(
        is_approved=False
    ).count()
    
    # Prepare context based on role
    context = {
        'role': role,
        'notifications': notifications,
        'pending_requests': pending_requests
    }
    
    # Add role-specific stats
    if role in ['admin', 'academic_admin']:
        context.update({
            'total_exams': total_exams,
            'total_teachers': total_teachers,
            'published_exams': published_exams
        })
    elif role == 'exam_coordinator':
        context.update({
            'total_exams': total_exams,
            'published_exams': published_exams
        })
    elif role == 'teacher':
        context['assigned_subjects_count'] = assigned_subjects_count
    
    return render(request, 'academic/dashboard.html', context)


@login_required
def mark_notifications_read(request):
    Notification.objects.filter(
        user=request.user,
        is_read=False
    ).update(is_read=True)
    messages.success(request, "Notifications marked as read.")
    return redirect(request.META.get('HTTP_REFERER') or 'academic_dashboard')


@login_required
def mark_notification_read(request, notification_id):
    Notification.objects.filter(
        id=notification_id,
        user=request.user
    ).update(is_read=True)
    return redirect(request.META.get('HTTP_REFERER') or 'all_notifications')


@login_required
def all_notifications(request):
    notifications = Notification.objects.filter(user=request.user).order_by('-created_at')

    paginator = Paginator(notifications, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'academic/notifications.html', {
        'page_obj': page_obj,
    })

# ===============================
# TEACHER SUBJECT LIST
# ===============================
@login_required
def teacher_subjects(request):

    subjects = TeacherSubject.objects.filter(
        teacher=request.user,
        is_active=True
    ).select_related('subject').order_by('student_class')

    query = request.GET.get('q', '').strip()
    level = request.GET.get('level', '').strip()

    if query:
        subjects = subjects.filter(
            Q(subject__name__icontains=query) |
            Q(subject__code__icontains=query) |
            Q(student_class__icontains=query)
        )

    if level in ['O', 'A']:
        subjects = subjects.filter(level=level)

    paginator = Paginator(subjects, 12)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'academic/teacher_subjects.html', {
        'page_obj': page_obj,
        'subjects': page_obj.object_list,
        'query': query,
        'filter_level': level,
    })


# ===============================
# SELECT EXAM
# ===============================
@login_required
def select_exam(request, subject_id, student_class):
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Check admin access
    is_admin = False
    if request.user.is_superuser:
        is_admin = True
    else:
        user_module = UserModule.objects.filter(
            user=request.user,
            module__name='academic',
            is_approved=True,
            is_admin=True
        ).first()
        if user_module:
            is_admin = True
    
    # Check assignment (skip for admins)
    if not is_admin:
        is_assigned = TeacherSubject.objects.filter(
            teacher=request.user,
            subject=subject,
            student_class=student_class,
            is_active=True
        ).exists()
        
        if not is_assigned:
            messages.error(request, "You are not assigned to this subject/class!")
            return redirect('teacher_subjects')
    
    # Get exams that apply to this class
    from django.db.models import Q
    
    # Determine which exam filters apply
    if student_class in ['Form 1', 'Form 2', 'Form 3', 'Form 4']:
        class_filters = Q(student_class=student_class) | Q(student_class='all_olevel') | Q(student_class='all')
    else:
        class_filters = Q(student_class=student_class) | Q(student_class='all_alevel') | Q(student_class='all')
    
    # Also show exams with no class specified (legacy)
    class_filters |= Q(student_class__isnull=True)
    
    # FIXED: Level filter - include BOTH subjects for A-Level exams
    # If subject level is 'BOTH', it can be taken at A-Level
    if subject.level == 'BOTH' and student_class in ['Form 5', 'Form 6']:
        # For A-Level classes, BOTH subjects should show A-Level exams
        level_filter = Q(level='A') | Q(level='ALL')
    elif subject.level == 'BOTH' and student_class in ['Form 1', 'Form 2', 'Form 3', 'Form 4']:
        # For O-Level classes, BOTH subjects should show O-Level exams
        level_filter = Q(level='O') | Q(level='ALL')
    else:
        # For specific level subjects
        level_filter = Q(level=subject.level) | Q(level='ALL')
    
    exams = Exam.objects.filter(
        class_filters,
        level_filter
    ).order_by('-created_at')
    
    if not exams.exists():
        messages.warning(request, f"No exams found for {student_class} - {subject.name}")
    
    return render(request, 'academic/select_exam.html', {
        'exams': exams,
        'subject': subject,
        'student_class': student_class
    })

@login_required
def enter_marks(request, exam_id, subject_id, student_class):

    exam = get_object_or_404(Exam, id=exam_id)
    subject = get_object_or_404(Subject, id=subject_id)
    class_level = get_class_level(student_class)
    is_admin = is_academic_admin(request.user)

    if not class_level:
        messages.error(request, "Invalid class selected.")
        return redirect('teacher_subjects')

    if subject.level != class_level or exam.level != class_level:
        messages.error(request, "Subject, class, and exam level do not match.")
        return redirect('teacher_subjects')

    if exam.student_class not in [student_class, 'all', 'all_olevel', 'all_alevel', None, '']:
        messages.error(request, "This exam does not apply to the selected class.")
        return redirect('teacher_subjects')

    if exam.student_class == 'all_olevel' and class_level != 'O':
        messages.error(request, "This exam is for O-Level classes only.")
        return redirect('teacher_subjects')

    if exam.student_class == 'all_alevel' and class_level != 'A':
        messages.error(request, "This exam is for A-Level classes only.")
        return redirect('teacher_subjects')

    # ===============================
    # ðŸ”’ SECURITY CHECKS
    # ===============================
    is_admin = request.user.is_superuser or UserModule.objects.filter(
        user=request.user,
        module__name='academic',
        is_approved=True,
        is_admin=True
    ).exists()

    if not is_admin:
        is_assigned = TeacherSubject.objects.filter(
            teacher=request.user,
            subject=subject,
            student_class=student_class,
            is_active=True
        ).exists()

        if not is_assigned:
            messages.error(request, "You are not assigned to this subject/class!")
            return redirect('teacher_subjects')

    # ===============================
    # ðŸ”’ EXAM STATUS
    # ===============================
    if exam.is_locked:
        messages.error(request, "This exam is locked.")
        return redirect('teacher_subjects')

    if exam.is_published:
        messages.error(request, "Results already published.")
        return redirect('teacher_subjects')

    # ===============================
    # ðŸš¨ LEVEL CHECK
    # ===============================
    if subject.level != exam.level:
        messages.error(request, "Subject does not belong to this exam level.")
        return redirect('teacher_subjects')

    # ===============================
    # ðŸ“Œ SUBMISSION CONTROL
    # ===============================
    submission, _ = MarkSubmission.objects.get_or_create(
        exam=exam,
        subject=subject,
        student_class=student_class
    )

    # ðŸ”¥ SOFT LOCK (ONLY ADMIN CAN EDIT WHEN LOCKED)
    if exam.is_locked and not is_admin:
        messages.error(request, "Marks are locked for this subject.")
        return redirect('teacher_subjects')

    # ===============================
    # ðŸŽ¯ GET STUDENTS
    # ===============================
    students = get_students_for_subject_class(subject, student_class)

    # ===============================
    # ðŸ“„ PAPERS
    # ===============================
    if exam.level == 'A':
        papers = Paper.objects.filter(subject=subject).order_by('paper_number')
    else:
        papers = Paper.objects.none()

    is_advanced = exam.level == 'A'

    # ===============================
    # ðŸ’¾ SAVE / SUBMIT MARKS
    # ===============================
    if request.method == 'POST':

        action = request.POST.get("action", "save")
        saved_count = 0
        errors = []

        # 🔒 One transaction for the whole batch — a mid-loop failure must
        # not leave some students' marks saved and others not.
        with transaction.atomic():
            for student in students:

                if is_advanced:
                    for paper in papers:

                        key = f"marks_{student.id}_p{paper.paper_number}"
                        value = request.POST.get(key)

                        if not value:
                            continue

                        value = value.strip().upper()

                        if value == "ABS":
                            StudentMark.objects.update_or_create(
                                student=student,
                                exam=exam,
                                subject=subject,
                                paper=paper,
                                defaults={
                                    'marks': 0,
                                    'is_absent': True,
                                    'uploaded_by': request.user
                                }
                            )
                            continue

                        try:
                            mark_value = float(value)

                            if 0 <= mark_value <= paper.max_marks:
                                StudentMark.objects.update_or_create(
                                    student=student,
                                    exam=exam,
                                    subject=subject,
                                    paper=paper,
                                    defaults={
                                        'marks': mark_value,
                                        'is_absent': False,
                                        'uploaded_by': request.user
                                    }
                                )
                                saved_count += 1
                            else:
                                errors.append(f"{student} P{paper.paper_number} invalid")

                        except ValueError:
                            errors.append(f"{student} P{paper.paper_number} not a number")

                else:
                    key = f"marks_{student.id}"
                    value = request.POST.get(key)

                    if not value:
                        continue

                    value = value.strip().upper()

                    if value == "ABS":
                        StudentMark.objects.update_or_create(
                            student=student,
                            exam=exam,
                            subject=subject,
                            paper=None,
                            defaults={
                                'marks': 0,
                                'is_absent': True,
                                'uploaded_by': request.user
                            }
                        )
                        continue

                    try:
                        mark_value = float(value)

                        if 0 <= mark_value <= 100:
                            StudentMark.objects.update_or_create(
                                student=student,
                                exam=exam,
                                subject=subject,
                                paper=None,
                                defaults={
                                    'marks': mark_value,
                                    'is_absent': False,
                                    'uploaded_by': request.user
                                }
                            )
                            saved_count += 1
                        else:
                            errors.append(f"{student} invalid mark")

                    except ValueError:
                        errors.append(f"{student} not a number")

        # ===============================
        # ðŸ“Œ SUBMIT (SOFT)
        # ===============================
        if action == "submit":
            submission.is_submitted = True
            submission.submitted_by = request.user
            submission.submitted_at = timezone.now()
            submission.save()

            messages.success(request, "Marks submitted (still editable until admin locks).")
            
            # ðŸ”¥ STEP 2 â€” SUBMIT LOG
            log_action(
                user=request.user,
                action='update',
                instance=exam,
                module='academic',
                changes={
                    "event": "marks_submitted",
                    "subject": subject.name,
                    "class": student_class
                }
            )
        else:
            messages.success(request, f"{saved_count} marks saved.")
            
            # ðŸ”¥ STEP 2 â€” SAVE MARKS LOG
            log_action(
                user=request.user,
                action='update',
                instance=exam,
                module='academic',
                changes={
                    "event": "marks_saved",
                    "subject": subject.name,
                    "class": student_class,
                    "count": saved_count
                }
            )

        # ðŸ”¥ SHOW ERRORS (if any)
        if errors:
            for err in errors[:5]:
                messages.warning(request, err)

        return redirect('enter_marks', exam.id, subject.id, student_class)

    # ===============================
    # ðŸ“Š LOAD EXISTING MARKS
    # ===============================
    marks_dict = {}

    existing_marks = StudentMark.objects.filter(
        exam=exam,
        subject=subject,
        student__in=students
    ).select_related('paper', 'student')

    for mark in existing_marks:
        key = f"{mark.student.id}_p{mark.paper.paper_number}" if mark.paper else str(mark.student.id)
        marks_dict[key] = "ABS" if mark.is_absent else str(mark.marks)

    # ===============================
    # ðŸ“Š TOTALS
    # ===============================
    student_totals = {}

    for student in students:
        total = 0

        if is_advanced:
            for paper in papers:
                val = marks_dict.get(f"{student.id}_p{paper.paper_number}")
                if val and val != "ABS":
                    total += float(val)
        else:
            val = marks_dict.get(str(student.id))
            if val and val != "ABS":
                total = float(val)

        student_totals[student.id] = total

    return render(request, 'academic/enter_marks.html', {
        'students': students,
        'exam': exam,
        'subject': subject,
        'papers': papers,
        'marks_dict': marks_dict,
        'student_class': student_class,
        'is_advanced': is_advanced,
        'student_totals': student_totals,
        'submission': submission,
    })

@login_required
def unlock_marks(request, exam_id, subject_id, student_class):

    if not request.user.is_superuser:
        messages.error(request, "Only admin can unlock marks.")
        return redirect('exam_dashboard')

    submission = MarkSubmission.objects.filter(
        exam_id=exam_id,
        subject_id=subject_id,
        student_class=student_class
    ).first()

    if submission:
        submission.is_submitted = False
        submission.save()

        messages.success(request, "Marks unlocked successfully.")

    return redirect('exam_dashboard')

@login_required
def clear_subject_marks(request, exam_id, subject_id, student_class):
    """Clear all marks for a specific subject/exam/class"""
    
    exam = get_object_or_404(Exam, id=exam_id)
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Check permissions
    is_admin = request.user.is_superuser or UserModule.objects.filter(
        user=request.user,
        module__name='academic',
        is_approved=True,
        is_admin=True
    ).exists()
    
    if not is_admin:
        is_assigned = TeacherSubject.objects.filter(
            teacher=request.user,
            subject=subject,
            student_class=student_class,
            is_active=True
        ).exists()
        
        if not is_assigned:
            messages.error(request, "Access denied!")
            return redirect('teacher_subjects')
    
    if exam.is_locked or exam.is_published:
        messages.error(request, "Cannot clear marks for locked or published exam!")
        return redirect('enter_marks', exam_id=exam_id, subject_id=subject_id, student_class=student_class)
    
    # Delete marks
    deleted_count = StudentMark.objects.filter(
        exam=exam,
        subject=subject,
        student__student_class=student_class
    ).delete()[0]
    
    messages.success(request, f"ðŸ—‘ï¸ Cleared {deleted_count} mark records for {subject.name} - {exam.name}")
    
    # ðŸ”¥ STEP 9 â€” CLEAR MARKS LOG
    log_action(
        user=request.user,
        action='delete',
        instance=exam,
        module='academic',
        changes={
            "event": "marks_cleared",
            "subject": subject.name,
            "count": deleted_count
        }
    )
    
    return redirect('enter_marks', exam_id=exam_id, subject_id=subject_id, student_class=student_class)

# ===============================
# EXAM DASHBOARD
# ===============================
@login_required
def exam_dashboard(request):
    # Show ALL exams - no filtering by creator
    exams = Exam.objects.all().order_by('-created_at')
    
    return render(request, 'academic/exam_dashboard.html', {
        'exams': exams
    })


# ===============================
# CREATE EXAM
@login_required
def create_exam(request, exam_id=None):

    if not can_manage_results(request.user):
        messages.error(request, "Access denied! Only admins or exam coordinators can manage exams.")
        return redirect('exam_dashboard')

    current_year = AcademicYear.get_current_year()
    years = AcademicYear.objects.filter(is_active=True)
    exam = None

    if exam_id:
        exam = get_object_or_404(Exam, id=exam_id)

    if request.method == 'POST':
        name = request.POST.get('name')
        level = request.POST.get('level')
        term = request.POST.get('term')
        student_class = request.POST.get('student_class')
        year_id = request.POST.get('year')

        # ===============================
        # ðŸ”¥ NORMALIZE CLASS (VERY IMPORTANT)
        # ===============================
        if not student_class or student_class.strip() == "":
            student_class = 'all'

        student_class = student_class.strip()

        # ===============================
        # ðŸš¨ VALIDATION (LEVEL vs CLASS)
        # ===============================
        o_classes = ['Form 1', 'Form 2', 'Form 3', 'Form 4']
        a_classes = ['Form 5', 'Form 6']

        if level == 'A' and student_class in o_classes:
            messages.error(request, "A-Level exams cannot target O-Level classes!")
            return redirect('create_exam')

        if level == 'O' and student_class in a_classes:
            messages.error(request, "O-Level exams cannot target A-Level classes!")
            return redirect('create_exam')

        # ===============================
        # ðŸ“… YEAR
        # ===============================
        year = AcademicYear.objects.filter(id=year_id).first() or current_year

        # ===============================
        # âœï¸ UPDATE EXAM
        # ===============================
        if exam:
            exam.name = name
            exam.level = level
            exam.term = term
            exam.student_class = student_class
            exam.academic_year = year
            exam.save()
            
            # ðŸ”¥ STEP 3 â€” UPDATE LOG
            log_action(
                user=request.user,
                action='update',
                instance=exam,
                module='academic',
                changes={
                    "exam": exam.name,
                    "class": exam.student_class,
                    "level": exam.level
                }
            )

            action_msg = "updated"

        # ===============================
        # âž• CREATE EXAM
        # ===============================
        else:
            exam = Exam.objects.create(
                name=name,
                level=level,
                term=term,
                student_class=student_class,
                academic_year=year,
                created_by=request.user
            )
            
            # ðŸ”¥ STEP 3 â€” CREATE LOG
            log_action(
                user=request.user,
                action='create',
                instance=exam,
                module='academic',
                changes={
                    "exam": exam.name,
                    "class": exam.student_class,
                    "level": exam.level
                }
            )

            action_msg = "created"

        # ===============================
        # ðŸ§  FRIENDLY DISPLAY NAME
        # ===============================
        class_display_map = {
            'all': 'All Classes (Form 1-6)',
            'all_olevel': 'All O-Level (Form 1-4)',
            'all_alevel': 'All A-Level (Form 5-6)',
        }

        class_display = class_display_map.get(student_class, student_class)

        # ===============================
        # âœ… SUCCESS MESSAGE
        # ===============================
        messages.success(
            request,
            f"âœ… Exam '{name}' {action_msg} for {class_display}!"
        )

        return redirect('exam_dashboard')

    # ===============================
    # ðŸ“¦ CONTEXT
    # ===============================
    context = {
        'years': years,
        'exam': exam,
        'terms': Exam.TERM_CHOICES,
        'level_choices': Exam.LEVEL_CHOICES,
        'classes_list': ACADEMIC_CLASSES,
    }

    return render(request, 'academic/create_exam.html', context)

@login_required
def delete_exam(request, exam_id):

    if not can_manage_results(request.user):
        messages.error(request, "Access denied! Only admins or exam coordinators can delete exams.")
        return redirect('exam_dashboard')

    exam = get_object_or_404(Exam, id=exam_id)

    # ðŸ” SAFETY CHECK
    has_results = Result.objects.filter(exam=exam).exists()

    if has_results:
        messages.error(request, "âŒ Cannot delete exam with results!")
        return redirect('exam_dashboard')
    
    exam_name = exam.name  # Store before delete
    exam.delete()
    
    # ðŸ”¥ STEP 4 â€” DELETE LOG
    log_action(
        user=request.user,
        action='delete',
        instance=exam,  # Note: exam instance is deleted but we still have the variable
        module='academic',
        changes={
            "exam": exam_name
        }
    )

    messages.success(request, "ðŸ—‘ï¸ Exam deleted successfully!")

    return redirect('exam_dashboard')

# ===============================
# LOCK / UNLOCK EXAM
# ===============================
@login_required
def toggle_lock_exam(request, exam_id):

    if not can_manage_results(request.user):
        messages.error(request, "Access denied! Only admins or exam coordinators can lock/unlock exams.")
        return redirect('exam_dashboard')

    exam = get_object_or_404(Exam, id=exam_id)

    exam.is_locked = not exam.is_locked

    if exam.is_locked:
        exam.locked_at = timezone.now()
        messages.success(request, "Exam locked successfully!")
    else:
        exam.locked_at = None
        messages.success(request, "Exam unlocked!")

    exam.save()
    
    # ðŸ”¥ STEP 5 â€” LOCK/UNLOCK LOG
    log_action(
        user=request.user,
        action='update',
        instance=exam,
        module='academic',
        changes={
            "locked": exam.is_locked
        }
    )

    return redirect('exam_dashboard')

# ===============================
# GENERATE RESULTS
# ===============================
@login_required
def generate_results(request, exam_id):

    exam = get_object_or_404(Exam, id=exam_id)

    # ðŸ” PERMISSION CHECK
    if not can_manage_results(request.user):
        messages.error(request, "You are not allowed to generate results")
        return redirect('exam_dashboard')

    # ðŸš« DO NOT GENERATE IF ALREADY PUBLISHED
    if exam.is_published:
        messages.error(request, "Results already published")
        return redirect('exam_dashboard')

    # ðŸŽ¯ GET STUDENTS BASED ON EXAM CLASS
    students = get_students_for_exam(exam)
    ranked_results = rank_students(students, exam)

    created = 0
    for r in ranked_results:
        Result.objects.update_or_create(
            exam=exam,
            student=r["student"],
            defaults={
                "total_points": r["points"],
                "division": r["division"],
                "position": r["position"]
            }
        )
        created += 1

    messages.success(request, f"{created} results generated successfully")
    
    # ðŸ”¥ STEP 6 â€” GENERATE RESULTS LOG
    log_action(
        user=request.user,
        action='update',
        instance=exam,
        module='academic',
        changes={
            "event": "results_generated",
            "count": created
        }
    )

    return redirect('exam_dashboard')


# ===============================
# PUBLISH RESULTS
# ===============================
@login_required
def publish_results(request, exam_id):

    exam = get_object_or_404(Exam, id=exam_id)

    # ðŸ” PERMISSION
    if not can_manage_results(request.user):
        messages.error(request, "You are not allowed to publish results")
        return redirect('exam_dashboard')

    # ðŸš« ALREADY PUBLISHED
    if exam.is_published:
        messages.warning(request, "Results already published")
        return redirect('exam_dashboard')

    # âŒ CHECK RESULTS EXIST
    has_results = Result.objects.filter(exam=exam).exists()
    if not has_results:
        messages.error(request, "Generate results first before publishing")
        return redirect('exam_dashboard')

    # âŒ CHECK MARKS COMPLETENESS (IMPORTANT)
    students = get_students_for_exam(exam)

    if not students.exists():
        messages.error(request, "No active students found for this exam.")
        return redirect('exam_dashboard')

    required_subjects = 7 if exam.level == 'O' else 3

    subject_counts = dict(
        StudentMark.objects.filter(exam=exam, student__in=students)
        .values('student')
        .annotate(subject_count=Count('subject', distinct=True))
        .values_list('student', 'subject_count')
    )

    incomplete_students = [
        student for student in students
        if subject_counts.get(student.id, 0) < required_subjects
    ]

    if incomplete_students:
        sample = ", ".join(
            student.registration_number for student in incomplete_students[:5]
        )
        messages.error(
            request,
            f"Cannot publish. {len(incomplete_students)} student(s) have fewer than "
            f"{required_subjects} subject results. Check: {sample}"
        )
        return redirect('exam_dashboard')

    # âœ… PUBLISH
    exam.is_published = True
    exam.is_locked = True
    exam.show_marks = True
    exam.save()
    
    # ðŸ”¥ STEP 7 â€” PUBLISH RESULTS LOG
    log_action(
        user=request.user,
        action='update',
        instance=exam,
        module='academic',
        changes={
            "event": "results_published"
        }
    )

    if exam.student_class == 'all':
        relevant_classes = ACADEMIC_CLASSES
    elif exam.student_class == 'all_olevel':
        relevant_classes = ["Form 1", "Form 2", "Form 3", "Form 4"]
    elif exam.student_class == 'all_alevel':
        relevant_classes = ["Form 5", "Form 6"]
    else:
        relevant_classes = [exam.student_class]

    assigned_teachers = User.objects.filter(
        teachersubject__student_class__in=relevant_classes,
        teachersubject__level=exam.level,
        teachersubject__is_active=True
    ).distinct()

    notify_many(
        assigned_teachers,
        f"Results for '{exam.name}' have been published.",
        email=True,
        email_subject="Exam results published",
    )
    notify_module_admins(
        'academic',
        f"Results for '{exam.name}' have been published.",
    )

    messages.success(request, "Results published and exam locked")

    return redirect('exam_dashboard')


@login_required
def unpublish_results(request, exam_id):

    exam = get_object_or_404(Exam, id=exam_id)

    # ðŸ” PERMISSION (only admin level should unpublish)
    if not request.user.is_superuser:
        is_admin = UserModule.objects.filter(
            user=request.user,
            module__name='academic',
            is_admin=True,
            is_approved=True
        ).exists()

        if not is_admin:
            messages.error(request, "Only academic admin can unpublish results")
            return redirect('exam_dashboard')

    # ðŸš« IF NOT PUBLISHED
    if not exam.is_published:
        messages.warning(request, "Results are not published")
        return redirect('exam_dashboard')

    # ðŸ”“ UNPUBLISH
    exam.is_published = False
    exam.is_locked = False
    exam.save()
    
    # ðŸ”¥ STEP 8 â€” UNPUBLISH RESULTS LOG
    log_action(
        user=request.user,
        action='update',
        instance=exam,
        module='academic',
        changes={
            "event": "results_unpublished"
        }
    )

    messages.success(request, "Results unpublished and exam unlocked")

    return redirect('exam_dashboard')

# ===============================
# CLASS RESULTS (RANKING LIST)
# ===============================
@login_required
def class_results(request, exam_id, student_class):

    exam = get_object_or_404(Exam, id=exam_id)

    # ðŸ” ACCESS CONTROL
    if not exam.is_published and not request.user.is_staff:
        return redirect('academic_dashboard')

    # ===============================
    # ðŸŽ¯ SUBJECT FILTER (FIXED)
    # ===============================
    if exam.level == 'A':
        subjects = Subject.objects.filter(level__in=['A', 'BOTH'], is_active=True)
    else:
        subjects = Subject.objects.filter(level__in=['O', 'BOTH'], is_active=True)

    subjects = subjects.filter(
        studentmark__exam=exam,
        studentmark__student__student_class=student_class
    ).distinct()

    # ===============================
    # ðŸ“Š GET STUDENTS
    # ===============================
    students = Student.objects.filter(
        student_class=student_class,
        school_status='Active',
        is_archived=False
    )

    ranked_students = []

    for student in students:

        calc = calculate_student_result(student, exam)

        grades_dict = {}

        for sub in calc["subjects"]:
            if sub["subject"] in subjects:
                grades_dict[sub["subject"].id] = sub["grade"]

        ranked_students.append({
            'student': student,
            'grades': grades_dict,
            'total_marks_sum': calc["total_marks_sum"],
            'total_points': calc["total_points"],
            'division': calc["division"],
            'is_complete': calc["is_complete"]
        })

    # ===============================
    # ðŸ† SORT (LOW POINTS BEST)
    # ===============================
    ranked_students = sorted(
        ranked_students,
        key=lambda x: (not x['is_complete'], -x['total_marks_sum'], x['total_points'])
    )

    # ===============================
    # ðŸ… POSITION (HANDLE TIES)
    # ===============================
    position = 1
    for i, data in enumerate(ranked_students):
        if (
            i > 0
            and data['total_points'] == ranked_students[i-1]['total_points']
            and data['is_complete'] == ranked_students[i-1]['is_complete']
        ):
            data['position'] = ranked_students[i-1]['position']
        else:
            data['position'] = position
        position += 1

    return render(request, 'academic/class_results.html', {
        'selected_exam': exam,
        'selected_class': student_class,
        'subjects': subjects,
        'students_data': ranked_students
    })


@login_required
def select_class_results(request):

    exams = Exam.objects.filter(is_published=True).order_by('-created_at')

    classes = [
        'Form 1', 'Form 2', 'Form 3',
        'Form 4', 'Form 5', 'Form 6'
    ]

    return render(request, 'academic/class_results.html', {
        'exams': exams,
        'classes': classes,
        'selected_exam': None,
        'selected_class': None,
        'students_data': None,
        'subjects': None
    })


# ===============================
# STUDENT RESULT (DETAIL VIEW)
# ===============================
@login_required
def student_result_detail(request, exam_id, student_id):

    exam = get_object_or_404(Exam, id=exam_id)
    student = get_object_or_404(Student, id=student_id)

    # ===============================
    # ðŸ” ACCESS CONTROL
    # ===============================
    if not exam.is_published and not request.user.is_staff:
        return redirect('academic_dashboard')

    # ===============================
    # ðŸ§® CALCULATE RESULT
    # ===============================
    result_summary = calculate_student_result(student, exam)

    # ===============================
    # ðŸ† GET POSITION
    # ===============================
    result_obj = Result.objects.filter(
        exam=exam,
        student=student
    ).first()

    result_summary['position'] = result_obj.position if result_obj else None

    # ===============================
    # ðŸ“š PROCESS SUBJECTS (FULL FIX)
    # ===============================
    for sub in result_summary['subjects']:

        subject = sub['subject']

        marks_qs = StudentMark.objects.filter(
            student=student,
            exam=exam,
            subject=subject
        ).select_related('paper')

        papers = {}

        # âœ… CORRECT LOOP
        for mark in marks_qs:

            if mark.paper:
                paper_key = f"Paper {mark.paper.paper_number}"
            else:
                paper_key = "Main"

            papers[paper_key] = {
                "score": mark.marks,
                "is_absent": mark.is_absent
            }

        # âœ… attach papers
        sub['papers'] = papers

        # ===============================
        # ðŸš¨ ABSENT LOGIC
        # ===============================
        sub['is_absent'] = (
            all(p["is_absent"] for p in papers.values())
            if papers else False
        )

        # ===============================
        # ðŸ“Š TOTAL MARKS
        # ===============================
        sub['total_marks'] = sum(
            p["score"] for p in papers.values()
            if p["score"] is not None
        )

    # ===============================
    # ðŸ“¤ RENDER
    # ===============================
    return render(request, 'academic/student_result_detail.html', {
        'student': student,
        'exam': exam,
        'result': result_summary,
        'show_marks': exam.is_published or exam.show_marks
    })


@login_required
def transcript_center(request):
    if not can_manage_results(request.user):
        messages.error(request, "You are not allowed to download transcripts")
        return redirect('academic_dashboard')

    query = request.GET.get('q', '').strip()
    selected_class = request.GET.get('student_class', '').strip()
    selected_student_id = request.GET.get('student_id')

    students = Student.objects.filter(is_archived=False).order_by(
        'first_name', 'last_name'
    )

    if selected_class:
        students = students.filter(student_class=selected_class)

    if query:
        students = students.filter(
            Q(first_name__icontains=query) |
            Q(middle_name__icontains=query) |
            Q(last_name__icontains=query) |
            Q(registration_number__icontains=query)
        )

    selected_student = None
    published_results = Result.objects.none()

    if selected_student_id:
        selected_student = get_object_or_404(Student, id=selected_student_id)
        published_results = Result.objects.filter(
            student=selected_student,
            exam__is_published=True
        ).select_related('exam', 'exam__academic_year').order_by(
            '-exam__academic_year__year', '-exam__created_at'
        )

    return render(request, 'academic/transcripts.html', {
        'students': students[:100],
        'query': query,
        'selected_class': selected_class,
        'selected_student': selected_student,
        'published_results': published_results,
        'academic_classes': ACADEMIC_CLASSES,
    })


@login_required
def download_student_transcript(request, student_id):
    if not can_manage_results(request.user):
        messages.error(request, "You are not allowed to download transcripts")
        return redirect('academic_dashboard')

    student = get_object_or_404(Student, id=student_id)
    results = Result.objects.filter(
        student=student,
        exam__is_published=True
    ).select_related('exam', 'exam__academic_year').order_by(
        'exam__academic_year__year', 'exam__created_at'
    )

    if not results.exists():
        messages.error(request, "No published results found for this student")
        return redirect('transcript_center')

    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    import os

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = (
        f'attachment; filename="{student.registration_number}_transcript.pdf"'
    )

    doc = SimpleDocTemplate(
        response,
        pagesize=A4,
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1 * cm,
        bottomMargin=1 * cm
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'TranscriptTitle',
        parent=styles['Title'],
        fontSize=16,
        alignment=1,
        textColor=colors.HexColor('#12355b'),
        spaceAfter=4
    )
    section_style = ParagraphStyle(
        'TranscriptSection',
        parent=styles['Heading3'],
        fontSize=10,
        textColor=colors.HexColor('#12355b'),
        spaceBefore=10,
        spaceAfter=5
    )
    normal_small = ParagraphStyle(
        'TranscriptSmall',
        parent=styles['Normal'],
        fontSize=8,
        leading=10
    )
    normal_small_center = ParagraphStyle(
        'TranscriptSmallCenter',
        parent=normal_small,
        alignment=1
    )

    elements = []
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'school_logo.png')
    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=1.7 * cm, height=1.7 * cm))

    elements.append(Paragraph("DODOMA SECONDARY SCHOOL", title_style))
    elements.append(Paragraph("ACADEMIC TRANSCRIPT", styles['Heading2']))
    elements.append(Spacer(1, 8))

    student_name = f"{student.first_name} {student.middle_name or ''} {student.last_name or ''}".strip()
    student_info = [
        ["Name", student_name, "Registration No", student.registration_number],
        ["Class", student.student_class, "Section", student.section],
        ["Generated By", request.user.get_full_name() or request.user.username, "Status", student.school_status],
    ]
    info_table = Table(student_info, colWidths=[2.8 * cm, 5.3 * cm, 3 * cm, 5 * cm])
    info_table.setStyle(TableStyle([
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#cbd5e1')),
        ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f1f5f9')),
        ('BACKGROUND', (2, 0), (2, -1), colors.HexColor('#f1f5f9')),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 10))

    for result_obj in results:
        exam = result_obj.exam
        calc = calculate_student_result(student, exam)
        heading = (
            f"{exam.name} | {exam.academic_year.year} | "
            f"{exam.get_level_display()} | Points: {calc['total_points']} | {calc['division']}"
        )
        elements.append(Paragraph(heading, section_style))

        rows = [["Subject", "Marks", "Grade", "Points"]]
        for subject_result in calc["subjects"]:
            total_marks = "ABS" if subject_result["grade"] == "ABS" else str(subject_result.get("total_marks", "-"))
            
            # For A-Level, show paper breakdown in the Marks column
            marks_display = total_marks
            if exam.level == 'A' and subject_result.get("papers"):
                paper_marks = []
                for p in subject_result["papers"]:
                    if p["paper_number"]:
                        paper_marks.append(f"P{p['paper_number']}: {p['marks']}")
                
                if paper_marks:
                    breakdown = ", ".join(paper_marks)
                    marks_display = Paragraph(
                        f"{total_marks}<br/><font size='7' color='#475569'>({breakdown})</font>",
                        normal_small_center
                    )

            rows.append([
                Paragraph(subject_result["subject"].name, normal_small),
                marks_display,
                subject_result["grade"],
                subject_result["points"],
            ])

        result_table = Table(rows, colWidths=[8.3 * cm, 2.5 * cm, 2.4 * cm, 2.4 * cm])
        result_table.setStyle(TableStyle([
            ('GRID', (0, 0), (-1, -1), 0.35, colors.HexColor('#cbd5e1')),
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#12355b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 1), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))
        elements.append(result_table)

    doc.build(elements)

    log_action(
        user=request.user,
        action='export',
        instance=student,
        module='academic',
        changes={
            'export_type': 'student_transcript',
            'student': student.registration_number,
            'published_exams': results.count(),
        }
    )

    return response

# ===============================
# EXCEL UPLOAD MARKS
# ===============================
@login_required
def upload_marks_excel(request, exam_id, subject_id, student_class):

    exam = get_object_or_404(Exam, id=exam_id)
    subject = get_object_or_404(Subject, id=subject_id)
    class_level = get_class_level(student_class)
    is_admin = is_academic_admin(request.user)

    if not class_level:
        messages.error(request, "Invalid class selected.")
        return redirect('teacher_subjects')

    if subject.level != class_level or exam.level != class_level:
        messages.error(request, "Subject, class, and exam level do not match.")
        return redirect('teacher_subjects')

    if exam.student_class not in [student_class, 'all', 'all_olevel', 'all_alevel', None, '']:
        messages.error(request, "This exam does not apply to the selected class.")
        return redirect('teacher_subjects')

    if exam.student_class == 'all_olevel' and class_level != 'O':
        messages.error(request, "This exam is for O-Level classes only.")
        return redirect('teacher_subjects')

    if exam.student_class == 'all_alevel' and class_level != 'A':
        messages.error(request, "This exam is for A-Level classes only.")
        return redirect('teacher_subjects')

    is_assigned = TeacherSubject.objects.filter(
        teacher=request.user,
        subject=subject,
        student_class=student_class,
        is_active=True
    ).exists()

    if not is_assigned and not is_admin:
        messages.error(request, "You are not assigned to this subject/class!")
        return redirect('teacher_subjects')

    if exam.is_locked:
        messages.error(request, "Marks are locked!")
        return redirect('teacher_subjects')

    if exam.is_published:
        messages.error(request, "Results already published!")
        return redirect('teacher_subjects')

    students = get_students_for_subject_class(subject, student_class)
    valid_students = {
        student.registration_number.strip().upper(): student
        for student in students
    }
    papers = list(Paper.objects.filter(subject=subject).order_by('paper_number'))
    is_advanced_level = class_level == 'A'

    if request.method == 'POST' and request.FILES.get('file'):

        file = request.FILES['file']
        if not file.name.lower().endswith('.xlsx'):
            messages.error(request, "Upload an .xlsx Excel file.")
            return redirect('upload_marks_excel', exam.id, subject.id, student_class)

        try:
            wb = openpyxl.load_workbook(file, read_only=True, data_only=True)
        except Exception:
            messages.error(request, "The Excel file could not be opened. Save it as .xlsx and try again.")
            return redirect('upload_marks_excel', exam.id, subject.id, student_class)

        sheet = wb.active
        success_count = 0
        skipped_count = 0
        error_rows = []

        if sheet.max_row < 2:
            messages.error(request, "The Excel file has no student rows.")
            return redirect('upload_marks_excel', exam.id, subject.id, student_class)

        with transaction.atomic():
            for row_number, row in enumerate(sheet.iter_rows(min_row=2, values_only=True), start=2):

                if not row or not row[0]:
                    continue

                reg_no = str(row[0]).strip().upper()
                student = valid_students.get(reg_no)

                if not student:
                    skipped_count += 1
                    error_rows.append(f"Row {row_number}: {reg_no} is not an active valid student for {subject.name} in {student_class}.")
                    continue

                if not is_advanced_level:
                    mark, is_absent, error = parse_excel_mark(row[1] if len(row) > 1 else None)

                    if mark is None and not is_absent:
                        if error:
                            error_rows.append(f"Row {row_number}: marks {error}.")
                        continue

                    if not is_absent and not 0 <= mark <= 100:
                        error_rows.append(f"Row {row_number}: marks must be between 0 and 100.")
                        continue

                    StudentMark.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        paper=None,
                        defaults={
                            'marks': mark,
                            'is_absent': is_absent,
                            'uploaded_by': request.user,
                            'last_updated_by': request.user,
                        }
                    )
                    success_count += 1
                    continue

                if not papers:
                    messages.error(request, f"No papers are configured for {subject.name}.")
                    return redirect('upload_marks_excel', exam.id, subject.id, student_class)

                for index, paper in enumerate(papers, start=1):
                    value = row[index] if len(row) > index else None
                    mark, is_absent, error = parse_excel_mark(value)

                    if mark is None and not is_absent:
                        if error:
                            error_rows.append(f"Row {row_number} P{paper.paper_number}: marks {error}.")
                        continue

                    if not is_absent and not 0 <= mark <= paper.max_marks:
                        error_rows.append(f"Row {row_number} P{paper.paper_number}: marks must be between 0 and {paper.max_marks}.")
                        continue

                    StudentMark.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        paper=paper,
                        defaults={
                            'marks': mark,
                            'is_absent': is_absent,
                            'uploaded_by': request.user,
                            'last_updated_by': request.user,
                        }
                    )
                    success_count += 1

        MarkSubmission.objects.get_or_create(
            exam=exam,
            subject=subject,
            student_class=student_class
        )

        log_action(
            user=request.user,
            action='update',
            instance=exam,
            module='academic',
            changes={
                "event": "excel_marks_uploaded",
                "subject": subject.name,
                "class": student_class,
                "saved_count": success_count,
                "skipped_count": skipped_count,
                "error_count": len(error_rows),
            }
        )

        if skipped_count > 0:
            messages.warning(request, f"{success_count} marks uploaded. {skipped_count} rows skipped because the student is not valid for this subject/class.")
        else:
            messages.success(request, f"{success_count} marks uploaded successfully.")

        if error_rows:
            for error in error_rows[:8]:
                messages.warning(request, error)
            if len(error_rows) > 8:
                messages.warning(request, f"{len(error_rows) - 8} more row issues were hidden.")

        return redirect('enter_marks', exam.id, subject.id, student_class)

    return render(request, 'academic/upload_marks_excel.html', {
        'exam': exam,
        'subject': subject,
        'student_class': student_class,
        'papers': papers,
        'is_advanced_level': is_advanced_level,
        'valid_students_count': len(valid_students),
        'sample_students': list(students[:5]),
    })
# ===============================
# DOWNLOAD PDFS
# ===============================
@login_required
def download_student_pdf(request, exam_id, student_id):

    exam = get_object_or_404(Exam, id=exam_id)
    student = get_object_or_404(Student, id=student_id)

    # 🔐 ACCESS CONTROL
    if not exam.is_published and not request.user.is_staff:
        return redirect('academic_dashboard')

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{student.first_name}_result.pdf"'

    generate_student_pdf(response, student, exam)

    return response


@login_required
def download_class_pdf_for_class(request, exam_id, student_class):

    exam = get_object_or_404(Exam, id=exam_id)

    # 🔐 ACCESS CONTROL
    if not exam.is_published and not request.user.is_staff:
        return redirect('academic_dashboard')

    students = Student.objects.filter(
        student_class=student_class,
        school_status='Active'
    )

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{student_class}_results.pdf"'

    generate_class_pdf(response, students, exam)

    return response


# ===============================
# ACADEMIC USERS MANAGEMENT
# ===============================
@login_required
def academic_users(request):

    if not is_academic_admin(request.user):
        messages.error(request, "Access denied! Admins only.")
        return redirect('exam_dashboard')

    user_modules = UserModule.objects.filter(
        module__name='academic'
    ).select_related('user')

    query = request.GET.get('q', '').strip()
    status = request.GET.get('status', '').strip()
    role = request.GET.get('role', '').strip()

    if query:
        user_modules = user_modules.filter(
            Q(user__username__icontains=query) |
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query)
        )

    if status == 'approved':
        user_modules = user_modules.filter(is_approved=True)
    elif status == 'pending':
        user_modules = user_modules.filter(is_approved=False)

    if role == 'admin':
        user_modules = user_modules.filter(is_admin=True)
    elif role == 'coordinator':
        user_modules = user_modules.filter(is_exam_coordinator=True)
    elif role == 'teacher':
        user_modules = user_modules.filter(is_admin=False, is_exam_coordinator=False)

    user_modules = user_modules.order_by('is_approved', 'user__first_name', 'user__username')
    paginator = Paginator(user_modules, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'academic/academic_users.html', {
        'user_modules': page_obj.object_list,
        'page_obj': page_obj,
        'query': query,
        'filter_status': status,
        'filter_role': role,
    })


@login_required
def approve_academic_user(request, user_id):

    if not is_academic_admin(request.user):
        messages.error(request, "Access denied! Admins only.")
        return redirect('academic_users')

    user = get_object_or_404(User, id=user_id)

    UserModule.objects.filter(
        user=user,
        module__name='academic'
    ).update(is_approved=True)

    messages.success(request, "User approved!")

    return redirect(request.META.get('HTTP_REFERER', 'academic_users'))


@login_required
def assign_subjects(request, user_id):

    if not is_academic_admin(request.user):
        messages.error(request, "Access denied! Admins only.")
        return redirect('academic_users')

    user = get_object_or_404(User, id=user_id)

    classes = ACADEMIC_CLASSES

    # ===============================
    # ðŸ”¥ DETERMINE LEVEL FROM CLASS
    # ===============================
    def get_level(student_class):
        if student_class in ["Form 1", "Form 2", "Form 3", "Form 4"]:
            return 'O'
        elif student_class in ["Form 5", "Form 6"]:
            return 'A'
        return None

    if request.method == 'POST':

        subject_ids = request.POST.getlist('subjects')
        student_class = request.POST.get('class_select')

        if not student_class:
            messages.error(request, "âŒ Please select a class!")
            return redirect('assign_subjects', user_id=user_id)

        level = get_class_level(student_class)

        if not level:
            messages.error(request, "âŒ Invalid class selected!")
            return redirect('assign_subjects', user_id=user_id)

        if not subject_ids:
            messages.error(request, "âŒ Please select at least one subject!")
            return redirect('assign_subjects', user_id=user_id)

        assigned_count = 0
        skipped_count = 0

        for subject_id in subject_ids:
            subject = get_object_or_404(Subject, id=subject_id)

            # ðŸ”¥ BLOCK WRONG LEVEL ASSIGNMENT
            if subject.level != level:
                skipped_count += 1
                continue

            existing = TeacherSubject.objects.filter(
                teacher=user,
                subject=subject,
                student_class=student_class
            ).first()

            if existing:
                if existing.is_active:
                    skipped_count += 1
                    continue

                existing.level = level
                existing.is_active = True
                existing.save(update_fields=['level', 'is_active'])
                assigned_count += 1
                continue

            TeacherSubject.objects.create(
                teacher=user,
                subject=subject,
                student_class=student_class,
                level=level,  # ðŸ”¥ IMPORTANT
                is_active=True
            )

            assigned_count += 1

            create_notification(
                user,
                f"âœ… Assigned {subject.name} for {student_class}"
            )

        if assigned_count > 0:
            messages.success(request, f"âœ… {assigned_count} subject(s) assigned!")
        if skipped_count > 0:
            messages.warning(request, f"âš ï¸ {skipped_count} skipped (already assigned or wrong level).")

        return redirect('assign_subjects', user_id=user_id)

    # ===============================
    # ðŸ”¥ SHOW SUBJECTS BY LEVEL (UI FIX)
    # ===============================
    subjects = Subject.objects.filter(is_active=True)

    assigned = TeacherSubject.objects.filter(
        teacher=user,
        is_active=True
    ).select_related('subject')

    assigned_o_count = assigned.filter(level='O').count()
    assigned_a_count = assigned.filter(level='A').count()

    return render(request, 'academic/assign_subjects.html', {
        'user': user,
        'subjects': subjects,
        'classes': ACADEMIC_CLASSES,
        'assigned': assigned,
        'assigned_o_count': assigned_o_count,
        'assigned_a_count': assigned_a_count
    })

# ===============================
# TEACHER SELECT SUBJECTS (REQUEST)
# ===============================
@login_required
def select_subjects(request):

    subjects = Subject.objects.filter(is_active=True)

    def get_level(student_class):
        if student_class in ["Form 1", "Form 2", "Form 3", "Form 4"]:
            return 'O'
        elif student_class in ["Form 5", "Form 6"]:
            return 'A'
        return None

    user_requests = TeacherSubjectRequest.objects.filter(
        teacher=request.user
    ).order_by('-created_at').select_related('subject')

    if request.method == 'POST':

        subject_ids = request.POST.getlist('subjects')
        student_class = request.POST.get('class')

        if not student_class:
            messages.error(request, "âŒ Please select a class!")
            return redirect('select_subjects')

        level = get_class_level(student_class)

        if not level:
            messages.error(request, "âŒ Invalid class selected!")
            return redirect('select_subjects')

        if not subject_ids:
            messages.error(request, "âŒ Select at least one subject!")
            return redirect('select_subjects')

        created_count = 0
        skipped_count = 0

        for subject_id in subject_ids:
            subject = Subject.objects.get(id=subject_id)

            # ðŸ”¥ BLOCK WRONG LEVEL
            if subject.level != level:
                skipped_count += 1
                continue

            if TeacherSubjectRequest.objects.filter(
                teacher=request.user,
                subject_id=subject_id,
                student_class=student_class,
                is_approved=False
            ).exists():
                skipped_count += 1
                continue

            if TeacherSubject.objects.filter(
                teacher=request.user,
                subject_id=subject_id,
                student_class=student_class,
                is_active=True
            ).exists():
                skipped_count += 1
                continue

            TeacherSubjectRequest.objects.create(
                teacher=request.user,
                subject=subject,
                student_class=student_class,
                level=level  # ðŸ”¥ IMPORTANT
            )

            created_count += 1

        if created_count > 0:
            messages.success(request, f"âœ… {created_count} request(s) sent!")
        if skipped_count > 0:
            messages.info(request, f"â„¹ï¸ {skipped_count} skipped.")

        return redirect('select_subjects')

    return render(request, 'academic/select_subjects.html', {
        'subjects': subjects,
        'user_requests': user_requests
    })

# ===============================
# VIEW ASSIGNED SUBJECTS (EDIT PAGE)
# ===============================
@login_required
def manage_my_subjects(request):

    subjects = TeacherSubject.objects.filter(
        teacher=request.user,
        is_active=True
    )

    return render(request, 'academic/manage_my_subjects.html', {
        'subjects': subjects
    })


# ===============================
# REMOVE SUBJECT (TEACHER SELF)
# ===============================
@login_required
def remove_subject(request, subject_id):

    subject = get_object_or_404(
        TeacherSubject,
        id=subject_id,
        teacher=request.user
    )

    subject.is_active = False
    subject.save()

    messages.success(request, "Subject removed!")

    return redirect('manage_my_subjects')


# ===============================
# ADMIN REMOVE TEACHER SUBJECT
# ===============================
@login_required
def admin_remove_subject(request, id):

    if not is_academic_admin(request.user):
        messages.error(request, "Access denied! Admins only.")
        return redirect('academic_users')

    subject = get_object_or_404(TeacherSubject, id=id)

    subject.is_active = False
    subject.save()

    messages.success(request, "Removed successfully!")

    return redirect(request.META.get('HTTP_REFERER', 'academic_users'))


# ===============================
# VIEW REQUESTS (ADMIN)
# ===============================
@login_required
def approve_subject_requests(request):
    # Only admins can access this
    if not request.user.is_superuser:
        user_module = UserModule.objects.filter(
            user=request.user,
            module__name='academic',
            is_approved=True,
            is_admin=True
        ).first()
        
        if not user_module:
            messages.error(request, "Access denied. Admin only.")
            return redirect('academic_dashboard')
    
    requests = TeacherSubjectRequest.objects.filter(
        is_approved=False
    ).select_related('teacher', 'subject').order_by('-created_at')
    
    return render(request, 'academic/approve_requests.html', {
        'requests': requests
    })

# ===============================
# APPROVE SINGLE REQUEST
# ===============================
@login_required
def approve_request(request, request_id):

    req = get_object_or_404(TeacherSubjectRequest, id=request_id)

    assignment, created = TeacherSubject.objects.get_or_create(
        teacher=req.teacher,
        subject=req.subject,
        student_class=req.student_class,
        defaults={
            'level': req.level,
            'is_active': True,
        }
    )
    if not created and not assignment.is_active:
        assignment.level = req.level
        assignment.is_active = True
        assignment.save(update_fields=['level', 'is_active'])

    req.is_approved = True
    req.save()

    # notification
    create_notification(
        req.teacher,
        f"You have been assigned {req.subject.name} - {req.student_class}"
    )

    messages.success(request, "Subject approved!")

    return redirect('approve_subject_requests')


# ===============================
# REJECT REQUEST
# ===============================
@login_required
def reject_request(request, request_id):

    req = get_object_or_404(TeacherSubjectRequest, id=request_id)

    if request.method == 'POST':
        reason = request.POST.get('reason')

        # notify teacher
        create_notification(
            req.teacher,
            f"Your subject request for {req.subject.name} ({req.student_class}) was rejected. Reason: {reason}"
        )

        req.delete()

        messages.warning(request, "Request rejected!")

        return redirect('approve_subject_requests')

    return render(request, 'academic/reject_request.html', {
        'request_obj': req
    })

# ===============================
# ACADEMIC ADMIN RESULTS OVERVIEW (NEW)
# ===============================
@login_required
def admin_results_overview(request):

    # ===============================
    # ðŸ” ACCESS CONTROL
    # ===============================
    is_admin = request.user.is_superuser or UserModule.objects.filter(
        user=request.user,
        module__name='academic',
        is_approved=True,
        is_admin=True
    ).exists()

    if not is_admin:
        messages.error(request, "Access denied.")
        return redirect('academic_dashboard')

    # ===============================
    # ðŸ“Š BASE DATA
    # ===============================
    exams = Exam.objects.all().order_by('-created_at')
    classes = ['Form 1','Form 2','Form 3','Form 4','Form 5','Form 6']

    selected_exam_id = request.GET.get('exam_id')
    selected_class = request.GET.get('student_class')

    selected_exam = None
    subjects_status = []
    results_data = None
    all_uploaded = False

    # ===============================
    # ðŸŽ¯ MAIN LOGIC
    # ===============================
    if selected_exam_id and selected_class:

        selected_exam = get_object_or_404(Exam, id=selected_exam_id)

        # ===============================
        # ðŸŽ¯ GET STUDENTS
        # ===============================
        students = Student.objects.filter(
            student_class=selected_class,
            school_status='Active'
        )

        total_students = students.count()

        # ===============================
        # ðŸŽ¯ GET SUBJECTS (FIXED PROPERLY)
        # ===============================
        if selected_exam.level == 'A':
            # A-LEVEL â†’ based on combinations
            combo_names = students.values_list('section', flat=True).distinct()

            subjects = Subject.objects.filter(
                level='A',
                combination__name__in=combo_names,
                is_active=True
            ).distinct()

        else:
            # O-LEVEL â†’ ONLY O subjects (NO A-level contamination)
            subjects = Subject.objects.filter(
                level='O',
                is_active=True
            ).distinct()

        # ===============================
        # ðŸŽ¯ PROCESS SUBJECT STATUS
        # ===============================
        all_uploaded = True
        subjects_status = []

        for subject in subjects:

            # ===============================
            # STUDENTS PER SUBJECT
            # ===============================
            if selected_exam.level == 'A':
                combos = Combination.objects.filter(subjects=subject)
                combo_names = combos.values_list('name', flat=True)

                subject_students = students.filter(section__in=combo_names)
            else:
                subject_students = students

            subject_total = subject_students.count()

            # ===============================
            # COUNT DISTINCT STUDENTS WITH MARKS
            # ===============================
            uploaded_count = StudentMark.objects.filter(
                exam=selected_exam,
                subject=subject,
                student__in=subject_students
            ).values('student').distinct().count()

            submission = MarkSubmission.objects.filter(
                exam=selected_exam,
                subject=subject,
                student_class=selected_class
            ).first()

            subject_marks = StudentMark.objects.filter(
                exam=selected_exam,
                subject=subject,
                student__in=subject_students
            ).select_related('paper')

            per_student = {}
            for mark in subject_marks:
                current = per_student.setdefault(mark.student_id, {'marks': 0.0, 'max': 0.0, 'absent': False})
                if mark.is_absent:
                    current['absent'] = True
                    continue
                current['marks'] += mark.marks
                current['max'] += mark.paper.max_marks if mark.paper else 100

            percentages = [
                (item['marks'] / item['max']) * 100
                for item in per_student.values()
                if item['max'] > 0 and not item['absent']
            ]
            average_score = round(sum(percentages) / len(percentages), 2) if percentages else None
            if average_score is None:
                average_grade = '-'
            elif selected_exam.level == 'A':
                average_grade = get_alevel_grade(average_score)[0]
            else:
                average_grade = get_olevel_grade(average_score)[0]

            # ===============================
            # STATUS LOGIC
            # ===============================
            has_any = uploaded_count > 0
            is_marked_for_all = uploaded_count == subject_total and subject_total > 0
            is_submitted = bool(submission and submission.is_submitted)
            is_complete = is_marked_for_all and is_submitted

            if not is_complete:
                all_uploaded = False

            subjects_status.append({
                'subject': subject,
                'uploaded': uploaded_count,
                'total': subject_total,
                'remaining': subject_total - uploaded_count,
                'is_uploaded': is_complete,
                'is_marked_for_all': is_marked_for_all,
                'is_submitted': is_submitted,
                'submitted_at': submission.submitted_at if submission else None,
                'has_any_marks': has_any,
                'percentage': int((uploaded_count / subject_total) * 100) if subject_total > 0 else 0,
                'average_score': average_score,
                'average_grade': average_grade,
            })

        # ===============================
        # ðŸ“Š RESULTS DATA
        # ===============================
        if all_uploaded:
            results = Result.objects.filter(
                exam=selected_exam,
                student__student_class=selected_class
            ).order_by('position')
        else:
            results = Result.objects.none()

        results_data = {
            'results': results,
            'count': results.count(),
            'total_students': total_students,
            'all_uploaded': all_uploaded,
            'can_generate': all_uploaded and not selected_exam.is_locked,
            'can_publish': selected_exam.is_locked and not selected_exam.is_published
        }

    # ===============================
    # ðŸŽ¯ RENDER
    # ===============================
    return render(request, 'academic/admin_results_overview.html', {
        'exams': exams,
        'classes': classes,
        'selected_exam': selected_exam,
        'selected_class': selected_class,
        'subjects_status': subjects_status,
        'results_data': results_data,
    })

# ===============================
# ADMIN VIEW CLASS MARKS DETAIL (NEW)
# ===============================
@login_required
def admin_view_class_marks(request, exam_id, student_class, subject_id):
    """Academic admin can see all marks for a specific subject/exam/class"""
    
    # Check admin access
    is_admin = False
    if request.user.is_superuser:
        is_admin = True
    else:
        user_module = UserModule.objects.filter(
            user=request.user,
            module__name='academic',
            is_approved=True,
            is_admin=True
        ).exists()
        if user_module:
            is_admin = True
    
    if not is_admin:
        messages.error(request, "Access denied.")
        return redirect('academic_dashboard')
    
    exam = get_object_or_404(Exam, id=exam_id)
    subject = get_object_or_404(Subject, id=subject_id)
    
    # Get students
    if subject.code == "GS":
        students = Student.objects.filter(
            student_class=student_class,
            school_status='Active'
        )
    else:
        if student_class in ['Form 5', 'Form 6']:
            combos = Combination.objects.filter(subjects=subject)
            if combos.exists():
                combo_names = [c.name for c in combos]
                students = Student.objects.filter(
                    student_class=student_class,
                    school_status='Active',
                    section__in=combo_names
                )
            else:
                students = Student.objects.none()
        else:
            students = Student.objects.filter(
                student_class=student_class,
                school_status='Active'
            )
    
    students = students.order_by('first_name', 'last_name')
    
    # Get papers for A-Level
    papers = Paper.objects.filter(subject=subject).order_by('paper_number')
    is_advanced = exam.level == 'A' and papers.exists()
    
    # Get existing marks in one query instead of per student/paper
    marks_index = {
        (mark.student_id, mark.paper_id): mark
        for mark in StudentMark.objects.filter(
            exam=exam,
            subject=subject,
            student__in=students
        )
    }

    marks_data = []
    total_uploaded = 0

    for student in students:
        student_marks = {}
        if is_advanced:
            for paper in papers:
                mark = marks_index.get((student.id, paper.id))
                if mark:
                    total_uploaded += 1
                    student_marks[f'paper_{paper.paper_number}'] = "ABS" if mark.is_absent else mark.marks
                else:
                    student_marks[f'paper_{paper.paper_number}'] = "Not uploaded"
        else:
            mark = marks_index.get((student.id, None))
            if mark:
                total_uploaded += 1
                student_marks['marks'] = "ABS" if mark.is_absent else mark.marks
            else:
                student_marks['marks'] = "Not uploaded"

        marks_data.append({
            'student': student,
            'marks': student_marks
        })
    
    upload_percentage = (total_uploaded / (len(students) * (len(papers) if is_advanced else 1))) * 100 if students else 0
    
    return render(request, 'academic/admin_view_class_marks.html', {
        'exam': exam,
        'subject': subject,
        'student_class': student_class,
        'students': students,
        'marks_data': marks_data,
        'papers': papers,
        'is_advanced': is_advanced,
        'total_uploaded': total_uploaded,
        'total_expected': len(students) * (len(papers) if is_advanced else 1),
        'upload_percentage': round(upload_percentage, 2)
    })


from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.template.loader import render_to_string


@login_required
def manage_teacher_subjects(request):

    # ðŸ” Admin check
    if not request.user.is_superuser:
        user_module = UserModule.objects.filter(
            user=request.user,
            module__name='academic',
            is_approved=True,
            is_admin=True
        ).first()
        if not user_module:
            messages.error(request, "Access denied. Admin only.")
            return redirect('academic_dashboard')

    # ðŸŽ¯ Filters
    filter_class = request.GET.get('class')
    filter_subject = request.GET.get('subject')
    filter_teacher = request.GET.get('teacher')
    filter_level = request.GET.get('level')
    query = request.GET.get('q', '').strip()
    page_number = request.GET.get('page', 1)

    # Get subjects and classes for filters
    subjects = Subject.objects.filter(is_active=True)
    classes = ACADEMIC_CLASSES

    # ðŸ“¦ Get TeacherSubject objects directly (NOT dictionaries)
    assignments = TeacherSubject.objects.filter(is_active=True)\
        .select_related('teacher', 'subject')

    # Apply filters
    if filter_class and filter_class != 'None':
        assignments = assignments.filter(student_class=filter_class)
    if filter_subject and filter_subject != 'None':
        assignments = assignments.filter(subject_id=filter_subject)
    if filter_teacher and filter_teacher != 'None':
        assignments = assignments.filter(teacher_id=filter_teacher)
    if filter_level and filter_level != 'None':
        assignments = assignments.filter(level=filter_level)
    if query:
        assignments = assignments.filter(
            Q(teacher__username__icontains=query) |
            Q(teacher__first_name__icontains=query) |
            Q(teacher__last_name__icontains=query) |
            Q(subject__name__icontains=query) |
            Q(subject__code__icontains=query) |
            Q(student_class__icontains=query)
        )

    # Order by teacher name then subject
    assignments = assignments.order_by('teacher__first_name', 'teacher__last_name', 'subject__name')

    # ðŸ“„ Paginate assignments directly (10 per page)
    paginator = Paginator(assignments, 10)
    page_obj = paginator.get_page(page_number)

    # Get all academic users for filter dropdown
    all_users = User.objects.filter(
        Q(usermodule__module__name='academic', usermodule__is_approved=True) |
        Q(is_superuser=True)
    ).distinct().order_by('first_name', 'last_name')

    # Calculate stats
    stats = {
        'total_users': all_users.count(),
        'total_assignments': TeacherSubject.objects.filter(is_active=True).count(),
        'total_subjects_used': TeacherSubject.objects.filter(is_active=True).values('subject').distinct().count(),
        'total_classes_used': TeacherSubject.objects.filter(is_active=True).values('student_class').distinct().count(),
    }

    return render(request, 'academic/manage_teacher_subjects.html', {
        'page_obj': page_obj,  # This contains TeacherSubject objects
        'subjects': subjects,
        'classes': classes,
        'stats': stats,
        'filter_class': filter_class,
        'filter_subject': filter_subject,
        'filter_teacher': filter_teacher,
        'filter_level': filter_level,
        'query': query,
        'users_list': all_users,
    })

def get_user_academic_role(user):
    if user.is_superuser:
        return "System Admin"

    user_module = UserModule.objects.filter(
        user=user,
        module__name='academic',
        is_approved=True
    ).first()

    if user_module:
        if user_module.is_admin:
            return "Academic Admin"
        elif user_module.is_exam_coordinator:
            return "Exam Coordinator"
        else:
            return "Teacher"

    return "Unknown"

@login_required
def edit_teacher_assignment(request, assignment_id):
    """Edit or remove a specific teacher-subject assignment"""
    
    assignment = get_object_or_404(TeacherSubject, id=assignment_id, is_active=True)
    
    # Check admin access
    if not request.user.is_superuser:
        user_module = UserModule.objects.filter(
            user=request.user,
            module__name='academic',
            is_approved=True,
            is_admin=True
        ).first()
        if not user_module:
            messages.error(request, "Access denied. Admin only.")
            return redirect('academic_dashboard')
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'remove':
            assignment.is_active = False
            assignment.save()
            
            # Notify teacher
            create_notification(
                assignment.teacher,
                f"âŒ Your assignment for {assignment.subject.name} ({assignment.student_class}) has been removed."
            )
            
            messages.success(request, f"Removed {assignment.subject.name} from {assignment.teacher.get_full_name()}")
            return redirect('manage_teacher_subjects')
        
        elif action == 'change_class':
            new_class = request.POST.get('new_class')
            if new_class:
                new_level = get_class_level(new_class)
                if not new_level:
                    messages.error(request, "Invalid class selected.")
                    return redirect('edit_teacher_assignment', assignment_id=assignment.id)
                if assignment.subject.level != new_level:
                    messages.error(request, f"{assignment.subject.name} does not belong to {new_class}.")
                    return redirect('edit_teacher_assignment', assignment_id=assignment.id)

                # Check if assignment already exists for new class
                existing = TeacherSubject.objects.filter(
                    teacher=assignment.teacher,
                    subject=assignment.subject,
                    student_class=new_class
                ).exclude(id=assignment.id).first()
                
                if existing:
                    messages.error(request, f"This teacher already teaches {assignment.subject.name} in {new_class}!")
                else:
                    assignment.student_class = new_class
                    assignment.level = new_level
                    assignment.save()
                    
                    # Notify teacher
                    create_notification(
                        assignment.teacher,
                        f"ðŸ”„ Your {assignment.subject.name} class changed to {new_class}"
                    )
                    
                    messages.success(request, f"Updated class to {new_class}")
        
        return redirect('manage_teacher_subjects')
    
    classes = ACADEMIC_CLASSES
    
    return render(request, 'academic/edit_teacher_assignment.html', {
        'assignment': assignment,
        'classes': classes,
    })

@login_required
def bulk_assign_subjects(request):

    # ===============================
    # ðŸ”’ ADMIN CHECK
    # ===============================
    if not request.user.is_superuser:
        user_module = UserModule.objects.filter(
            user=request.user,
            module__name='academic',
            is_approved=True,
            is_admin=True
        ).first()

        if not user_module:
            messages.error(request, "Access denied.")
            return redirect('academic_dashboard')

    # ===============================
    # ðŸ“¥ POST
    # ===============================
    if request.method == 'POST':

        teacher_ids = request.POST.getlist('teachers')
        subject_ids = request.POST.getlist('subjects')
        student_class = request.POST.get('class')

        if not teacher_ids or not subject_ids or not student_class:
            messages.error(request, "Select teachers, subjects and class.")
            return redirect('bulk_assign_subjects')

        level = get_class_level(student_class)

        if not level:
            messages.error(request, "Invalid class.")
            return redirect('bulk_assign_subjects')

        assigned = 0
        skipped = 0

        for teacher_id in teacher_ids:
            teacher = get_object_or_404(User, id=teacher_id)

            for subject_id in subject_ids:
                subject = get_object_or_404(Subject, id=subject_id)

                # ðŸš« STRICT LEVEL MATCH
                if subject.level != level:
                    skipped += 1
                    continue

                obj, created = TeacherSubject.objects.get_or_create(
                    teacher=teacher,
                    subject=subject,
                    student_class=student_class,
                    defaults={
                        'level': level,
                        'is_active': True
                    }
                )

                if not created:
                    if obj.is_active:
                        skipped += 1
                        continue

                    obj.is_active = True
                    obj.level = level
                    obj.save()
                else:
                    assigned += 1

                create_notification(
                    teacher,
                    f"Assigned {subject.name} for {student_class}"
                )

        messages.success(request, f"{assigned} assigned successfully")
        if skipped:
            messages.warning(request, f"{skipped} skipped")

        return redirect('manage_teacher_subjects')

    # ===============================
    # ðŸ“Š GET
    # ===============================
    teachers = User.objects.filter(
        usermodule__module__name='academic',
        usermodule__is_approved=True
    ).distinct()

    subjects = Subject.objects.filter(is_active=True)

    classes = ACADEMIC_CLASSES

    return render(request, 'academic/bulk_assign_subjects.html', {
        'teachers': teachers,
        'subjects': subjects,
        'classes': classes,
    })

from .utils import calculate_student_result, rank_students
from registration.models import Student

@login_required
def class_results_view(request):
    # ===============================
    # ðŸ“Œ GET PUBLISHED EXAMS ONLY
    # ===============================
    exams = Exam.objects.filter(is_published=True).order_by('-created_at')

    classes = [
        'Form 1', 'Form 2', 'Form 3',
        'Form 4', 'Form 5', 'Form 6'
    ]

    selected_exam_id = request.GET.get('exam_id')
    selected_class = request.GET.get('class')

    selected_exam = None
    students_data = []
    subjects = []

    # ===============================
    # ðŸš€ MAIN LOGIC
    # ===============================
    if selected_exam_id and selected_class:
        selected_exam = get_object_or_404(Exam, id=selected_exam_id)

        # âœ… GET STUDENTS FOR THIS CLASS ONLY
        students = Student.objects.filter(
            student_class=selected_class,
            school_status='Active',
            is_archived=False
        )

        # âœ… FILTER ONLY STUDENTS WHO HAVE MARKS
        students = students.filter(
            studentmark__exam=selected_exam
        ).distinct()

        # âŒ if no students â†’ stop early
        if not students.exists():
            return render(request, 'academic/class_results.html', {
                'exams': exams,
                'classes': classes,
                'selected_exam': selected_exam,
                'selected_class': selected_class,
                'students_data': [],
                'subjects': []
            })

        # ===============================
        # ðŸ“š GET SUBJECTS
        # ===============================
        subjects = Subject.objects.filter(
            studentmark__exam=selected_exam,
            studentmark__student__student_class=selected_class
        ).distinct()

        # ===============================
        # ðŸ§® RANK STUDENTS
        # ===============================
        ranked = rank_students(students, selected_exam)

        for r in ranked:

            # âŒ skip empty students
            if all(sub["grade"] == "-" for sub in r["subjects"]):
                continue

            # âœ… BUILD GRADES DICTIONARY (IMPORTANT FIX)
            grades_dict = {}
            for sub in r["subjects"]:
                grades_dict[sub["subject"].id] = sub["grade"]

            students_data.append({
                'student': r["student"],
                'position': r["position"],
                'division': r["division"],
                'total_points': r["points"],
                'is_complete': r["is_complete"],
                'grades': grades_dict
            })

    # ===============================
    # ðŸ“¤ RETURN
    # ===============================
    return render(request, 'academic/class_results.html', {
        'exams': exams,
        'classes': classes,
        'selected_exam': selected_exam,
        'selected_class': selected_class,
        'students_data': students_data,
        'subjects': subjects
    })

from django.http import HttpResponse
from django.template.loader import get_template
from xhtml2pdf import pisa

from .utils import calculate_student_result, rank_students
from registration.models import Student


@login_required
def download_class_pdf(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    # 🔐 ACCESS CONTROL
    if not exam.is_published and not request.user.is_staff:
        return redirect('academic_dashboard')

    students = Student.objects.filter(
        studentmark__exam=exam
    ).distinct()

    ranked = rank_students(students, exam)

    students_data = []

    for r in ranked:
        # skip empty students
        if all(sub["grade"] in ["-", "ABS"] for sub in r["subjects"]):
            continue

        students_data.append({
            'student': r["student"],
            'position': r["position"],
            'division': r["division"],
            'points': r["points"],
            'subjects_data': r["subjects"]
        })

    subjects = []
    if students_data:
        subjects = [s["subject"] for s in students_data[0]["subjects_data"]]

    template = get_template('academic/pdf/class_results_pdf.html')
    html = template.render({
        'exam': exam,
        'students_data': students_data,
        'subjects': subjects,
        'logo_path': str(settings.BASE_DIR / 'static' / 'images' / 'school_logo.png'),
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="class_results_{exam.id}.pdf"'

    pisa.CreatePDF(html, dest=response)

    return response
