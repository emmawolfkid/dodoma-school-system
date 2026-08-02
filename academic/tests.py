from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import User, Module, UserModule
from registration.models import Student

from .models import AcademicYear, Subject, Exam, StudentMark
from .utils import (
    get_olevel_grade,
    get_alevel_grade,
    calculate_olevel_division,
    calculate_alevel_division,
    calculate_student_result,
    rank_students,
)


def make_student(reg_no, student_class='Form 1', section='A'):
    return Student.objects.create(
        registration_number=reg_no, first_name='Test', last_name=reg_no,
        gender='Male', date_of_birth='2006-01-01', student_class=student_class, section=section,
        date_of_admission='2022-01-01', region='X', district='X', ward='X', village='X',
        parent_name='X', parent_phone='0712345678', health_status='Fit',
    )


class GradingBoundaryTests(TestCase):
    """
    NECTA CSEE (O-Level) and ACSEE (A-Level) grade/division boundaries,
    confirmed against the classic 7-subject point-sum system this school
    actually uses.
    """

    def test_olevel_grade_boundaries(self):
        self.assertEqual(get_olevel_grade(75), ('A', 1))
        self.assertEqual(get_olevel_grade(74.99), ('B', 2))
        self.assertEqual(get_olevel_grade(65), ('B', 2))
        self.assertEqual(get_olevel_grade(45), ('C', 3))
        self.assertEqual(get_olevel_grade(30), ('D', 4))
        self.assertEqual(get_olevel_grade(29.99), ('F', 5))
        self.assertEqual(get_olevel_grade(0), ('F', 5))

    def test_alevel_grade_boundaries(self):
        self.assertEqual(get_alevel_grade(80), ('A', 1))
        self.assertEqual(get_alevel_grade(70), ('B', 2))
        self.assertEqual(get_alevel_grade(60), ('C', 3))
        self.assertEqual(get_alevel_grade(50), ('D', 4))
        self.assertEqual(get_alevel_grade(40), ('E', 5))
        self.assertEqual(get_alevel_grade(35), ('S', 6))
        self.assertEqual(get_alevel_grade(34.99), ('F', 7))

    def test_olevel_division_boundaries(self):
        self.assertEqual(calculate_olevel_division(7), "Division I")
        self.assertEqual(calculate_olevel_division(17), "Division I")
        self.assertEqual(calculate_olevel_division(18), "Division II")
        self.assertEqual(calculate_olevel_division(21), "Division II")
        self.assertEqual(calculate_olevel_division(22), "Division III")
        self.assertEqual(calculate_olevel_division(25), "Division III")
        self.assertEqual(calculate_olevel_division(26), "Division IV")
        self.assertEqual(calculate_olevel_division(33), "Division IV")
        self.assertEqual(calculate_olevel_division(34), "Division 0")

    def test_alevel_division_boundaries(self):
        self.assertEqual(calculate_alevel_division(3), "Division I")
        self.assertEqual(calculate_alevel_division(9), "Division I")
        self.assertEqual(calculate_alevel_division(10), "Division II")
        self.assertEqual(calculate_alevel_division(12), "Division II")
        self.assertEqual(calculate_alevel_division(13), "Division III")
        self.assertEqual(calculate_alevel_division(15), "Division III")
        self.assertEqual(calculate_alevel_division(16), "Division IV")
        self.assertEqual(calculate_alevel_division(18), "Division IV")
        self.assertEqual(calculate_alevel_division(19), "Division 0")


class CalculateStudentResultTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(year='2026')
        self.exam = Exam.objects.create(name='Mock', level='O', academic_year=self.year, student_class='Form 1')
        self.student = make_student('RES-1')
        self.math = Subject.objects.create(name='Math', code='MATH1', level='O')
        self.eng = Subject.objects.create(name='English', code='ENG1', level='O')

    def test_average_marks_excludes_absent_subjects_from_denominator(self):
        """
        Regression test: average_marks used to divide total_marks_sum
        (which excludes absent subjects) by len(results) (which includes
        them), silently understating the average.
        """
        StudentMark.objects.create(student=self.student, exam=self.exam, subject=self.math, marks=80)
        StudentMark.objects.create(student=self.student, exam=self.exam, subject=self.eng, is_absent=True, marks=0)

        result = calculate_student_result(self.student, self.exam)

        self.assertEqual(result['total_marks_sum'], 80)
        # Average must be over the ONE marked subject, not both.
        self.assertEqual(result['average_marks'], 80)


class StudentMarkUniqueConstraintTests(TestCase):
    def setUp(self):
        self.year = AcademicYear.objects.create(year='2026')
        self.exam = Exam.objects.create(name='Mock', level='O', academic_year=self.year, student_class='Form 1')
        self.student = make_student('RES-2')
        self.math = Subject.objects.create(name='Math', code='MATH2', level='O')

    def test_duplicate_olevel_mark_blocked_at_db_level(self):
        """
        Regression test: unique_together on a nullable `paper` field doesn't
        work on Postgres (NULL != NULL), which used to let concurrent
        submits create duplicate O-Level marks. Now enforced via a
        conditional UniqueConstraint.
        """
        StudentMark.objects.create(student=self.student, exam=self.exam, subject=self.math, paper=None, marks=50)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                StudentMark.objects.create(student=self.student, exam=self.exam, subject=self.math, paper=None, marks=60)


class RankingConsistencyTests(TestCase):
    """
    Regression test: class_results_view() used to compute its own ranking
    independently of rank_students() (used to persist Result.position),
    with different sort keys -- a student's position could disagree
    between the class list and their transcript. Both now share one rule.
    """

    def setUp(self):
        self.year = AcademicYear.objects.create(year='2026')
        self.exam = Exam.objects.create(name='Mock', level='O', academic_year=self.year, student_class='Form 1')
        self.subjects = [
            Subject.objects.create(name=f'Subj{i}', code=f'S{i}', level='O')
            for i in range(7)
        ]
        self.top_student = make_student('RANK-TOP')
        self.bottom_student = make_student('RANK-BOTTOM')
        for subj in self.subjects:
            StudentMark.objects.create(student=self.top_student, exam=self.exam, subject=subj, marks=90)
            StudentMark.objects.create(student=self.bottom_student, exam=self.exam, subject=subj, marks=40)

    def test_rank_students_orders_best_result_first(self):
        ranked = rank_students(Student.objects.filter(id__in=[self.top_student.id, self.bottom_student.id]), self.exam)
        self.assertEqual(ranked[0]['student'], self.top_student)
        self.assertEqual(ranked[0]['position'], 1)
        self.assertEqual(ranked[1]['student'], self.bottom_student)

    def test_rank_students_includes_subjects_breakdown(self):
        """rank_students() now carries the full subject breakdown so callers
        don't need to call calculate_student_result() a second time."""
        ranked = rank_students(Student.objects.filter(id=self.top_student.id), self.exam)
        self.assertIn('subjects', ranked[0])
        self.assertEqual(len(ranked[0]['subjects']), 7)


class ExamPermissionTests(TestCase):
    """
    Regression tests: create_exam/delete_exam/toggle_lock_exam/
    approve_academic_user/assign_subjects/academic_users/
    admin_remove_subject used to have no role check at all -- any
    logged-in user (even an unapproved one) could call them.
    """

    def setUp(self):
        self.module, _ = Module.objects.get_or_create(name='academic')
        self.plain_user = User.objects.create_user(username='plain', password='StrongPass123', is_approved=True)
        self.admin_user = User.objects.create_user(username='acadadmin', password='StrongPass123', is_approved=True)
        UserModule.objects.create(user=self.admin_user, module=self.module, is_admin=True, is_approved=True)
        self.year = AcademicYear.objects.create(year='2026')
        self.exam = Exam.objects.create(name='Mock', level='O', academic_year=self.year, student_class='Form 1')

    def test_plain_user_cannot_toggle_lock(self):
        self.client.force_login(self.plain_user)
        self.client.post(reverse('toggle_lock_exam', args=[self.exam.id]))
        self.exam.refresh_from_db()
        self.assertFalse(self.exam.is_locked)

    def test_module_admin_can_toggle_lock(self):
        self.client.force_login(self.admin_user)
        self.client.post(reverse('toggle_lock_exam', args=[self.exam.id]))
        self.exam.refresh_from_db()
        self.assertTrue(self.exam.is_locked)

    def test_plain_user_cannot_delete_exam(self):
        self.client.force_login(self.plain_user)
        self.client.post(reverse('delete_exam', args=[self.exam.id]))
        self.assertTrue(Exam.objects.filter(id=self.exam.id).exists())

    def test_plain_user_cannot_approve_academic_users(self):
        target = User.objects.create_user(username='pendingteacher', password='StrongPass123', is_approved=True)
        um = UserModule.objects.create(user=target, module=self.module, is_approved=False)

        self.client.force_login(self.plain_user)
        self.client.post(reverse('approve_academic_user', args=[target.id]))

        um.refresh_from_db()
        self.assertFalse(um.is_approved)


class ResultPdfAccessTests(TestCase):
    """Regression test: result PDF downloads used to skip the
    is_published/is_staff gate that the HTML result pages enforce."""

    def setUp(self):
        self.year = AcademicYear.objects.create(year='2026')
        self.exam = Exam.objects.create(
            name='Mock', level='O', academic_year=self.year, student_class='Form 1', is_published=False
        )
        self.student = make_student('PDF-1')
        self.viewer = User.objects.create_user(username='viewer', password='StrongPass123', is_approved=True, is_superuser=True)

    def test_unpublished_pdf_blocked_for_non_staff(self):
        non_staff = User.objects.create_user(username='nonstaff', password='StrongPass123', is_approved=True, is_staff=False)
        UserModule.objects.create(
            user=non_staff, module=Module.objects.get_or_create(name='academic')[0], is_approved=True
        )
        self.client.force_login(non_staff)
        response = self.client.get(reverse('download_student_pdf', args=[self.exam.id, self.student.id]))
        self.assertEqual(response.status_code, 302)
        self.assertNotEqual(response.get('Content-Type'), 'application/pdf')
