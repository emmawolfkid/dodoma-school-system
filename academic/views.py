from django.shortcuts import render, get_object_or_404, redirect, reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db.models import Q
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage

import openpyxl

from accounts.models import User, UserModule
from registration.models import Student
from .models import TeacherSubject, Exam, StudentMark, Subject, AcademicYear, Result, Paper, TeacherSubjectRequest, Notification, Combination, MarkSubmission
from .utils import calculate_student_result, rank_students
from .utils_notifications import create_notification
from .pdf_utils import generate_student_pdf, generate_class_pdf


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


# ===============================
# ACADEMIC DASHBOARD
# ===============================
@login_required
def academic_dashboard(request):
    user = request.user
    
    # 🔥 SUPERUSER
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
        
        # 🔥 ROLE DETECTION
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
    
    # 🔔 NOTIFICATIONS
    notifications = Notification.objects.filter(
        user=request.user,
        is_read=False
    ).order_by('-created_at')[:5]
    
    # 📋 REQUEST COUNT
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

# ===============================
# TEACHER SUBJECT LIST
# ===============================
@login_required
def teacher_subjects(request):

    subjects = TeacherSubject.objects.filter(
        teacher=request.user,
        is_active=True
    ).select_related('subject').order_by('student_class')

    return render(request, 'academic/teacher_subjects.html', {
        'subjects': subjects
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
    
    # Debug output
    print(f"=== SELECT EXAM DEBUG ===")
    print(f"Subject: {subject.name} (level: '{subject.level}')")
    print(f"Student class: '{student_class}'")
    print(f"Level filter: {level_filter}")
    print(f"Exams found: {exams.count()}")
    for e in exams:
        print(f"  - {e.name}: class='{e.student_class}', level='{e.level}'")
    print(f"=========================")
    
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

    # ===============================
    # 🔒 SECURITY CHECKS
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
    # 🔒 EXAM STATUS
    # ===============================
    if exam.is_locked:
        messages.error(request, "This exam is locked.")
        return redirect('teacher_subjects')

    if exam.is_published:
        messages.error(request, "Results already published.")
        return redirect('teacher_subjects')

    # ===============================
    # 🚨 LEVEL CHECK
    # ===============================
    if subject.level != exam.level:
        messages.error(request, "Subject does not belong to this exam level.")
        return redirect('teacher_subjects')

    # ===============================
    # 📌 SUBMISSION CONTROL
    # ===============================
    submission, _ = MarkSubmission.objects.get_or_create(
        exam=exam,
        subject=subject,
        student_class=student_class
    )

    # 🔥 SOFT LOCK (ONLY ADMIN CAN EDIT WHEN LOCKED)
    if exam.is_locked and not is_admin:
        messages.error(request, "Marks are locked for this subject.")
        return redirect('teacher_subjects')

    # ===============================
    # 🎯 GET STUDENTS
    # ===============================
    students = Student.objects.filter(
        student_class__iexact=student_class.strip(),
        school_status='Active',
        is_archived=False
    )

    # ===============================
    # 🎓 A-LEVEL FILTERING (FIXED)
    # ===============================
    if exam.level == 'A':

        subject_code = subject.code.upper().strip() if subject.code else ""

        # ✅ GS_A → ALL STUDENTS
        if subject_code.startswith("GS"):
            pass

        else:
            combos = Combination.objects.filter(subjects=subject)

            if combos.exists():
                combo_names = [c.name.strip().upper() for c in combos]

                students = students.filter(
                    section__in=combo_names
                ).distinct()
            else:
                students = Student.objects.none()

    students = students.order_by('first_name', 'last_name')

    # ===============================
    # 📄 PAPERS
    # ===============================
    if exam.level == 'A':
        papers = Paper.objects.filter(subject=subject).order_by('paper_number')
    else:
        papers = Paper.objects.none()

    is_advanced = exam.level == 'A'

    # ===============================
    # 💾 SAVE / SUBMIT MARKS
    # ===============================
    if request.method == 'POST':

        action = request.POST.get("action", "save")
        saved_count = 0
        errors = []

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
        # 📌 SUBMIT (SOFT)
        # ===============================
        if action == "submit":
            submission.is_submitted = True
            submission.submitted_by = request.user
            submission.submitted_at = timezone.now()
            submission.is_locked = False  # 🔥 IMPORTANT FIX
            submission.save()

            messages.success(request, "Marks submitted (still editable until admin locks).")
        else:
            messages.success(request, f"{saved_count} marks saved.")

        # 🔥 SHOW ERRORS (if any)
        if errors:
            for err in errors[:5]:
                messages.warning(request, err)

        return redirect('enter_marks', exam.id, subject.id, student_class)

    # ===============================
    # 📊 LOAD EXISTING MARKS
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
    # 📊 TOTALS
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
        submission.is_locked = False
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
    
    messages.success(request, f"🗑️ Cleared {deleted_count} mark records for {subject.name} - {exam.name}")
    
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
        # 🔥 NORMALIZE CLASS (VERY IMPORTANT)
        # ===============================
        if not student_class or student_class.strip() == "":
            student_class = 'all'

        student_class = student_class.strip()

        # ===============================
        # 🚨 VALIDATION (LEVEL vs CLASS)
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
        # 📅 YEAR
        # ===============================
        year = AcademicYear.objects.filter(id=year_id).first() or current_year

        # ===============================
        # ✏️ UPDATE EXAM
        # ===============================
        if exam:
            exam.name = name
            exam.level = level
            exam.term = term
            exam.student_class = student_class
            exam.academic_year = year
            exam.save()

            action_msg = "updated"

        # ===============================
        # ➕ CREATE EXAM
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

            action_msg = "created"

        # ===============================
        # 🧠 FRIENDLY DISPLAY NAME
        # ===============================
        class_display_map = {
            'all': 'All Classes (Form 1-6)',
            'all_olevel': 'All O-Level (Form 1-4)',
            'all_alevel': 'All A-Level (Form 5-6)',
        }

        class_display = class_display_map.get(student_class, student_class)

        # ===============================
        # ✅ SUCCESS MESSAGE
        # ===============================
        messages.success(
            request,
            f"✅ Exam '{name}' {action_msg} for {class_display}!"
        )

        return redirect('exam_dashboard')

    # ===============================
    # 📦 CONTEXT
    # ===============================
    context = {
        'years': years,
        'exam': exam,
        'terms': Exam.TERM_CHOICES,
        'level_choices': Exam.LEVEL_CHOICES,
    }

    return render(request, 'academic/create_exam.html', context)

@login_required
def delete_exam(request, exam_id):

    exam = get_object_or_404(Exam, id=exam_id)

    # 🔐 SAFETY CHECK
    has_results = Result.objects.filter(exam=exam).exists()

    if has_results:
        messages.error(request, "❌ Cannot delete exam with results!")
        return redirect('exam_dashboard')

    exam.delete()

    messages.success(request, "🗑️ Exam deleted successfully!")

    return redirect('exam_dashboard')

# ===============================
# LOCK / UNLOCK EXAM
# ===============================
@login_required
def toggle_lock_exam(request, exam_id):

    exam = get_object_or_404(Exam, id=exam_id)

    exam.is_locked = not exam.is_locked

    if exam.is_locked:
        exam.locked_at = timezone.now()
        messages.success(request, "Exam locked successfully!")
    else:
        exam.locked_at = None
        messages.success(request, "Exam unlocked!")

    exam.save()

    return redirect('exam_dashboard')

# ===============================
# GENERATE RESULTS
# ===============================
@login_required
def generate_results(request, exam_id):

    exam = get_object_or_404(Exam, id=exam_id)

    # 🔐 PERMISSION CHECK
    if not can_manage_results(request.user):
        messages.error(request, "You are not allowed to generate results")
        return redirect('exam_dashboard')

    # 🚫 DO NOT GENERATE IF ALREADY PUBLISHED
    if exam.is_published:
        messages.error(request, "Results already published")
        return redirect('exam_dashboard')

    # 🎯 GET STUDENTS BASED ON EXAM CLASS
    if exam.student_class in ['Form 1', 'Form 2', 'Form 3', 'Form 4', 'Form 5', 'Form 6']:
        students = Student.objects.filter(
            student_class=exam.student_class,
            school_status='Active',
            is_archived=False
        )
    else:
        # fallback (for all classes exams)
        students = Student.objects.filter(
            school_status='Active',
            is_archived=False
        )

    created = 0

    for student in students:

        calc = calculate_student_result(student, exam)

        Result.objects.update_or_create(
            exam=exam,
            student=student,
            defaults={
                "total_points": calc.get("total_points", 0),
                "division": calc.get("division", "-")
            }
        )

        created += 1

    messages.success(request, f"{created} results generated successfully")

    return redirect('exam_dashboard')
# ===============================
# PUBLISH RESULTS
# ===============================
@login_required
def publish_results(request, exam_id):

    exam = get_object_or_404(Exam, id=exam_id)

    # 🔐 PERMISSION
    if not can_manage_results(request.user):
        messages.error(request, "You are not allowed to publish results")
        return redirect('exam_dashboard')

    # 🚫 ALREADY PUBLISHED
    if exam.is_published:
        messages.warning(request, "Results already published")
        return redirect('exam_dashboard')

    # ❌ CHECK RESULTS EXIST
    has_results = Result.objects.filter(exam=exam).exists()
    if not has_results:
        messages.error(request, "Generate results first before publishing")
        return redirect('exam_dashboard')

    # ❌ CHECK MARKS COMPLETENESS (IMPORTANT)
    students = Student.objects.filter(
        student_class=exam.student_class,
        school_status='Active',
        is_archived=False
    )

    total_students = students.count()

    subjects = Subject.objects.filter(
        studentmark__exam=exam
    ).distinct()

    incomplete = False

    for subject in subjects:
        uploaded = StudentMark.objects.filter(
            exam=exam,
            subject=subject,
            student__student_class=exam.student_class
        ).values('student').distinct().count()

        if uploaded < total_students:
            incomplete = True
            break

    if incomplete:
        messages.error(request, "Not all marks are entered. Cannot publish.")
        return redirect('exam_dashboard')

    # ✅ PUBLISH
    exam.is_published = True
    exam.is_locked = True
    exam.save()

    messages.success(request, "Results published and exam locked")

    return redirect('exam_dashboard')
@login_required
def unpublish_results(request, exam_id):

    exam = get_object_or_404(Exam, id=exam_id)

    # 🔐 PERMISSION (only admin level should unpublish)
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

    # 🚫 IF NOT PUBLISHED
    if not exam.is_published:
        messages.warning(request, "Results are not published")
        return redirect('exam_dashboard')

    # 🔓 UNPUBLISH
    exam.is_published = False
    exam.is_locked = False
    exam.save()

    messages.success(request, "Results unpublished and exam unlocked")

    return redirect('exam_dashboard')

# ===============================
# CLASS RESULTS (RANKING LIST)
# ===============================
@login_required
def class_results(request, exam_id, student_class):

    exam = get_object_or_404(Exam, id=exam_id)

    # 🔐 ACCESS CONTROL
    if not exam.is_published and not request.user.is_staff:
        return redirect('academic_dashboard')

    # ===============================
    # 🎯 SUBJECT FILTER (FIXED)
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
    # 📊 GET STUDENTS
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
            'total_points': calc["total_points"],
            'division': calc["division"]
        })

    # ===============================
    # 🏆 SORT (LOW POINTS BEST)
    # ===============================
    ranked_students = sorted(ranked_students, key=lambda x: x['total_points'])

    # ===============================
    # 🏅 POSITION (HANDLE TIES)
    # ===============================
    position = 1
    for i, data in enumerate(ranked_students):
        if i > 0 and data['total_points'] == ranked_students[i-1]['total_points']:
            data['position'] = ranked_students[i-1]['position']
        else:
            data['position'] = position
        position += 1

    return render(request, 'academic/class_results.html', {
        'exam': exam,
        'student_class': student_class,
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
    # 🔐 ACCESS CONTROL
    # ===============================
    if not exam.is_published and not request.user.is_staff:
        return redirect('academic_dashboard')

    # ===============================
    # 🧮 CALCULATE RESULT
    # ===============================
    result_summary = calculate_student_result(student, exam)

    # ===============================
    # 🏆 GET POSITION
    # ===============================
    result_obj = Result.objects.filter(
        exam=exam,
        student=student
    ).first()

    result_summary['position'] = result_obj.position if result_obj else None

    # ===============================
    # 📚 PROCESS SUBJECTS (FULL FIX)
    # ===============================
    for sub in result_summary['subjects']:

        subject = sub['subject']

        marks_qs = StudentMark.objects.filter(
            student=student,
            exam=exam,
            subject=subject
        ).select_related('paper')

        papers = {}

        # ✅ CORRECT LOOP
        for mark in marks_qs:

            if mark.paper:
                paper_key = f"Paper {mark.paper.paper_number}"
            else:
                paper_key = "Main"

            papers[paper_key] = {
                "score": mark.marks,
                "is_absent": mark.is_absent
            }

        # ✅ attach papers
        sub['papers'] = papers

        # ===============================
        # 🚨 ABSENT LOGIC
        # ===============================
        sub['is_absent'] = (
            all(p["is_absent"] for p in papers.values())
            if papers else False
        )

        # ===============================
        # 📊 TOTAL MARKS
        # ===============================
        sub['total_marks'] = sum(
            p["score"] for p in papers.values()
            if p["score"] is not None
        )

    # ===============================
    # 📤 RENDER
    # ===============================
    return render(request, 'academic/student_result_detail.html', {
        'student': student,
        'exam': exam,
        'result': result_summary,
        'show_marks': exam.show_marks
    })

# ===============================
# EXCEL UPLOAD MARKS
# ===============================
@login_required
def upload_marks_excel(request, exam_id, subject_id, student_class):

    exam = get_object_or_404(Exam, id=exam_id)
    subject = get_object_or_404(Subject, id=subject_id)

    # CHECK TEACHER ASSIGNMENT
    is_assigned = TeacherSubject.objects.filter(
        teacher=request.user,
        subject=subject,
        student_class=student_class,
        is_active=True
    ).exists()

    if not is_assigned and not request.user.is_superuser:
        messages.error(request, "You are not assigned to this subject/class!")
        return redirect('teacher_subjects')

    # 🔒 LOCK CHECK
    if exam.is_locked:
        messages.error(request, "Marks are locked!")
        return redirect('teacher_subjects')

    # 📊 PUBLISHED CHECK
    if exam.is_published:
        messages.error(request, "Results already published!")
        return redirect('teacher_subjects')

    # ===============================
    # 🎯 GET VALID STUDENTS FOR THIS SUBJECT (A-LEVEL COMBINATION FILTER)
    # ===============================
    is_advanced_level = student_class in ['Form 5', 'Form 6']
    
    if is_advanced_level:
        # Get all combinations that have this subject
        relevant_combinations = Combination.objects.filter(subjects=subject)
        
        if relevant_combinations.exists():
            combination_names = [combo.name for combo in relevant_combinations]
            valid_reg_numbers = Student.objects.filter(
                student_class=student_class,
                school_status='Active',
                section__in=combination_names
            ).values_list('registration_number', flat=True)
            valid_reg_numbers = list(valid_reg_numbers)
        else:
            valid_reg_numbers = []
    else:
        # For O-Level, all students in the class are valid
        valid_reg_numbers = Student.objects.filter(
            student_class=student_class,
            school_status='Active'
        ).values_list('registration_number', flat=True)
        valid_reg_numbers = list(valid_reg_numbers)

    if request.method == 'POST' and request.FILES.get('file'):

        file = request.FILES['file']
        fs = FileSystemStorage()
        filename = fs.save(file.name, file)
        filepath = fs.path(filename)

        wb = openpyxl.load_workbook(filepath)
        sheet = wb.active

        success_count = 0
        skipped_count = 0

        for row in sheet.iter_rows(min_row=2, values_only=True):

            reg_no = str(row[0]).strip()

            # Check if student is valid for this subject
            if reg_no not in valid_reg_numbers:
                skipped_count += 1
                continue

            try:
                student = Student.objects.get(
                    registration_number=reg_no,
                    student_class=student_class
                )
            except Student.DoesNotExist:
                skipped_count += 1
                continue

            # O-LEVEL
            if exam.level == 'O':

                marks = row[1]

                if marks is not None:
                    StudentMark.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        paper=None,
                        defaults={
                            'marks': float(marks),
                            'uploaded_by': request.user
                        }
                    )
                    success_count += 1

            # A-LEVEL (PAPERS)
            else:

                p1, p2, p3 = row[1], row[2], row[3]

                papers = {
                    1: p1,
                    2: p2,
                    3: p3
                }

                for paper_no, value in papers.items():

                    if value is None:
                        continue

                    paper = Paper.objects.filter(
                        subject=subject,
                        paper_number=paper_no
                    ).first()

                    if not paper:
                        continue

                    StudentMark.objects.update_or_create(
                        student=student,
                        exam=exam,
                        subject=subject,
                        paper=paper,
                        defaults={
                            'marks': float(value),
                            'uploaded_by': request.user
                        }
                    )

                    success_count += 1

        if skipped_count > 0:
            messages.warning(request, f"✅ {success_count} records uploaded! ⚠️ {skipped_count} students skipped (not taking this subject)")
        else:
            messages.success(request, f"✅ {success_count} records uploaded successfully!")
            
        return redirect('teacher_subjects')

    return render(request, 'academic/upload_marks_excel.html', {
        'exam': exam,
        'subject': subject,
        'student_class': student_class
    })

# ===============================
# DOWNLOAD PDFS
# ===============================
@login_required
def download_student_pdf(request, exam_id, student_id):

    exam = get_object_or_404(Exam, id=exam_id)
    student = get_object_or_404(Student, id=student_id)

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{student.first_name}_result.pdf"'

    generate_student_pdf(response, student, exam)

    return response


@login_required
def download_class_pdf(request, exam_id, student_class):

    exam = get_object_or_404(Exam, id=exam_id)

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

    user_modules = UserModule.objects.filter(
        module__name='academic'
    ).select_related('user')

    return render(request, 'academic/academic_users.html', {
        'user_modules': user_modules
    })


@login_required
def approve_academic_user(request, user_id):

    user = get_object_or_404(User, id=user_id)

    UserModule.objects.filter(
        user=user,
        module__name='academic'
    ).update(is_approved=True)

    messages.success(request, "User approved!")

    return redirect(request.META.get('HTTP_REFERER', 'academic_users'))


@login_required
def assign_subjects(request, user_id):

    user = get_object_or_404(User, id=user_id)

    classes = ACADEMIC_CLASSES

    # ===============================
    # 🔥 DETERMINE LEVEL FROM CLASS
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
            messages.error(request, "❌ Please select a class!")
            return redirect('assign_subjects', user_id=user_id)

        level = get_class_level(student_class)

        if not level:
            messages.error(request, "❌ Invalid class selected!")
            return redirect('assign_subjects', user_id=user_id)

        if not subject_ids:
            messages.error(request, "❌ Please select at least one subject!")
            return redirect('assign_subjects', user_id=user_id)

        assigned_count = 0
        skipped_count = 0

        for subject_id in subject_ids:
            subject = get_object_or_404(Subject, id=subject_id)

            # 🔥 BLOCK WRONG LEVEL ASSIGNMENT
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
                level=level,  # 🔥 IMPORTANT
                is_active=True
            )

            assigned_count += 1

            create_notification(
                user,
                f"✅ Assigned {subject.name} for {student_class}"
            )

        if assigned_count > 0:
            messages.success(request, f"✅ {assigned_count} subject(s) assigned!")
        if skipped_count > 0:
            messages.warning(request, f"⚠️ {skipped_count} skipped (already assigned or wrong level).")

        return redirect('assign_subjects', user_id=user_id)

    # ===============================
    # 🔥 SHOW SUBJECTS BY LEVEL (UI FIX)
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
            messages.error(request, "❌ Please select a class!")
            return redirect('select_subjects')

        level = get_class_level(student_class)

        if not level:
            messages.error(request, "❌ Invalid class selected!")
            return redirect('select_subjects')

        if not subject_ids:
            messages.error(request, "❌ Select at least one subject!")
            return redirect('select_subjects')

        created_count = 0
        skipped_count = 0

        for subject_id in subject_ids:
            subject = Subject.objects.get(id=subject_id)

            # 🔥 BLOCK WRONG LEVEL
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
                level=level  # 🔥 IMPORTANT
            )

            created_count += 1

        if created_count > 0:
            messages.success(request, f"✅ {created_count} request(s) sent!")
        if skipped_count > 0:
            messages.info(request, f"ℹ️ {skipped_count} skipped.")

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
    # 🔐 ACCESS CONTROL
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
    # 📊 BASE DATA
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
    # 🎯 MAIN LOGIC
    # ===============================
    if selected_exam_id and selected_class:

        selected_exam = get_object_or_404(Exam, id=selected_exam_id)

        # ===============================
        # 🎯 GET STUDENTS
        # ===============================
        students = Student.objects.filter(
            student_class=selected_class,
            school_status='Active'
        )

        total_students = students.count()

        # ===============================
        # 🎯 GET SUBJECTS (FIXED PROPERLY)
        # ===============================
        if selected_exam.level == 'A':
            # A-LEVEL → based on combinations
            combo_names = students.values_list('section', flat=True).distinct()

            subjects = Subject.objects.filter(
                level='A',
                combination__name__in=combo_names,
                is_active=True
            ).distinct()

        else:
            # O-LEVEL → ONLY O subjects (NO A-level contamination)
            subjects = Subject.objects.filter(
                level='O',
                is_active=True
            ).distinct()

        # ===============================
        # 🎯 PROCESS SUBJECT STATUS
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

            # ===============================
            # STATUS LOGIC
            # ===============================
            has_any = uploaded_count > 0
            is_complete = uploaded_count == subject_total and subject_total > 0

            if not is_complete:
                all_uploaded = False

            subjects_status.append({
                'subject': subject,
                'uploaded': uploaded_count,
                'total': subject_total,
                'remaining': subject_total - uploaded_count,
                'is_uploaded': is_complete,
                'has_any_marks': has_any,
                'percentage': int((uploaded_count / subject_total) * 100) if subject_total > 0 else 0
            })

        # ===============================
        # 📊 RESULTS DATA
        # ===============================
        results = Result.objects.filter(
            exam=selected_exam,
            student__student_class=selected_class
        ).order_by('position')

        results_data = {
            'results': results,
            'count': results.count(),
            'total_students': total_students,
            'all_uploaded': all_uploaded,
            'can_generate': all_uploaded and not selected_exam.is_locked,
            'can_publish': selected_exam.is_locked and not selected_exam.is_published
        }

    # ===============================
    # 🎯 RENDER
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
    
    # Get existing marks
    marks_data = []
    total_uploaded = 0
    
    for student in students:
        student_marks = {}
        if is_advanced:
            for paper in papers:
                mark = StudentMark.objects.filter(
                    student=student,
                    exam=exam,
                    subject=subject,
                    paper=paper
                ).first()
                if mark:
                    total_uploaded += 1
                    student_marks[f'paper_{paper.paper_number}'] = "ABS" if mark.is_absent else mark.marks
                else:
                    student_marks[f'paper_{paper.paper_number}'] = "Not uploaded"
        else:
            mark = StudentMark.objects.filter(
                student=student,
                exam=exam,
                subject=subject,
                paper=None
            ).first()
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

    # 🔐 Admin check
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

    # 🎯 Filters
    filter_class = request.GET.get('class')
    filter_subject = request.GET.get('subject')
    filter_teacher = request.GET.get('teacher')
    filter_level = request.GET.get('level')
    page_number = request.GET.get('page', 1)

    # Get subjects and classes for filters
    subjects = Subject.objects.filter(is_active=True)
    classes = ACADEMIC_CLASSES

    # 📦 Get TeacherSubject objects directly (NOT dictionaries)
    assignments = TeacherSubject.objects.filter(is_active=True)\
        .select_related('teacher', 'subject')

    # Apply filters
    if filter_class:
        assignments = assignments.filter(student_class=filter_class)
    if filter_subject:
        assignments = assignments.filter(subject_id=filter_subject)
    if filter_teacher:
        assignments = assignments.filter(teacher_id=filter_teacher)
    if filter_level:
        assignments = assignments.filter(level=filter_level)

    # Order by teacher name then subject
    assignments = assignments.order_by('teacher__first_name', 'teacher__last_name', 'subject__name')

    # 📄 Paginate assignments directly (10 per page)
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
                f"❌ Your assignment for {assignment.subject.name} ({assignment.student_class}) has been removed."
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
                        f"🔄 Your {assignment.subject.name} class changed to {new_class}"
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
    # 🔒 ADMIN CHECK
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
    # 📥 POST
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

                # 🚫 STRICT LEVEL MATCH
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
    # 📊 GET
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
    # 📌 GET PUBLISHED EXAMS ONLY
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
    # 🚀 MAIN LOGIC
    # ===============================
    if selected_exam_id and selected_class:
        selected_exam = get_object_or_404(Exam, id=selected_exam_id)

        # ✅ GET STUDENTS FOR THIS CLASS ONLY
        students = Student.objects.filter(
            student_class=selected_class,
            school_status='Active',
            is_archived=False
        )

        # ✅ FILTER ONLY STUDENTS WHO HAVE MARKS
        students = students.filter(
            studentmark__exam=selected_exam
        ).distinct()

        # ❌ if no students → stop early
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
        # 📚 GET SUBJECTS
        # ===============================
        subjects = Subject.objects.filter(
            studentmark__exam=selected_exam,
            studentmark__student__student_class=selected_class
        ).distinct()

        # ===============================
        # 🧮 RANK STUDENTS
        # ===============================
        ranked = rank_students(students, selected_exam)

        for r in ranked:
            res = calculate_student_result(r["student"], selected_exam)

            # ❌ skip empty students
            if all(sub["grade"] == "-" for sub in res["subjects"]):
                continue

            # ✅ BUILD GRADES DICTIONARY (IMPORTANT FIX)
            grades_dict = {}
            for sub in res["subjects"]:
                grades_dict[sub["subject"].id] = sub["grade"]

            students_data.append({
                'student': r["student"],
                'position': r["position"],
                'division': r["division"],
                'total_points': r["points"],
                'grades': grades_dict
            })

    # ===============================
    # 📤 RETURN
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

    students = Student.objects.filter(
        studentmark__exam=exam
    ).distinct()

    ranked = rank_students(students, exam)

    students_data = []

    for r in ranked:
        res = calculate_student_result(r["student"], exam)

        # skip empty students
        if all(sub["grade"] in ["-", "ABS"] for sub in res["subjects"]):
            continue

        students_data.append({
            'student': r["student"],
            'position': r["position"],
            'division': r["division"],
            'points': r["points"],
            'subjects_data': res["subjects"]
        })

    subjects = []
    if students_data:
        subjects = [s["subject"] for s in students_data[0]["subjects_data"]]

    template = get_template('academic/pdf/class_results_pdf.html')
    html = template.render({
        'exam': exam,
        'students_data': students_data,
        'subjects': subjects
    })

    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="class_results_{exam.id}.pdf"'

    pisa.CreatePDF(html, dest=response)

    return response

