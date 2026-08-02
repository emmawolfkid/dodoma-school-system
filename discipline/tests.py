from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from registration.models import Student

from .forms import SuspensionForm
from .models import DisciplineCase, DisciplineAuditLog, SuspensionRecord


def make_student(reg_no='DISC-1'):
    return Student.objects.create(
        registration_number=reg_no, first_name='Test', last_name='Student',
        gender='Male', date_of_birth='2006-01-01', student_class='Form 1', section='A',
        date_of_admission='2022-01-01', region='X', district='X', ward='X', village='X',
        parent_name='X', parent_phone='0712345678', health_status='Fit',
    )


class SuspensionFormValidationTests(TestCase):
    """
    Regression test for the most serious bug found this session:
    validate_for_suspension() read self.cleaned_data before it existed
    (full_clean() never having run), raising AttributeError on every call.
    This meant NO discipline suspension could ever be recorded --
    add_case/edit_case 500'd every time action_taken == 'suspension'.
    """

    def test_empty_form_does_not_crash_and_reports_missing_fields(self):
        form = SuspensionForm({})
        result = form.validate_for_suspension()
        self.assertFalse(result)
        self.assertIn('start_date', form.errors)
        self.assertIn('end_date', form.errors)

    def test_valid_dates_pass(self):
        form = SuspensionForm({'start_date': '2026-01-01', 'end_date': '2026-01-10'})
        self.assertTrue(form.validate_for_suspension())

    def test_end_before_start_is_rejected(self):
        form = SuspensionForm({'start_date': '2026-01-10', 'end_date': '2026-01-01'})
        self.assertFalse(form.validate_for_suspension())


class AddCaseWithSuspensionTests(TestCase):
    """End-to-end regression test for the same bug via the actual view."""

    def setUp(self):
        self.admin = User.objects.create_user(username='discadmin', password='StrongPass123', is_approved=True, is_superuser=True)
        self.student = make_student()
        self.client.force_login(self.admin)

    def test_suspension_case_created_atomically(self):
        response = self.client.post(reverse('discipline:add_case', args=[self.student.id]), {
            'title': 'Fighting',
            'case_type': 'major',
            'description': 'Fought another student',
            'status': 'open',
            'severity_points': 5,
            'date_of_incident': '2026-01-01',
            'action_taken': 'suspension',
            'start_date': '2026-01-02',
            'end_date': '2026-01-09',
        })
        self.assertEqual(response.status_code, 302)
        case = DisciplineCase.objects.get(student=self.student)
        self.assertEqual(case.action_type, 'suspension')
        self.assertTrue(SuspensionRecord.objects.filter(case=case).exists())

    def test_invalid_suspension_leaves_no_orphaned_case(self):
        """A case must never persist with action_type='suspension' but no
        SuspensionRecord -- that used to crash later code accessing
        case.suspension."""
        response = self.client.post(reverse('discipline:add_case', args=[self.student.id]), {
            'title': 'Fighting',
            'case_type': 'major',
            'description': 'Fought another student',
            'status': 'open',
            'severity_points': 5,
            'date_of_incident': '2026-01-01',
            'action_taken': 'suspension',
            # start_date/end_date omitted -> invalid suspension
        })
        self.assertEqual(response.status_code, 200)  # re-renders the form with errors
        self.assertFalse(DisciplineCase.objects.filter(student=self.student).exists())


class CaseStateChangeIdempotencyTests(TestCase):
    """Regression test: resolve_case/archive_case had no guard against
    repeat clicks, producing duplicate DisciplineAuditLog rows."""

    def setUp(self):
        self.admin = User.objects.create_user(username='discadmin2', password='StrongPass123', is_approved=True, is_superuser=True)
        self.student = make_student('DISC-2')
        self.case = DisciplineCase.objects.create(
            student=self.student, reported_by=self.admin, case_type='minor',
            title='Late', description='Late to class', date_of_incident='2026-01-01',
        )
        self.client.force_login(self.admin)

    def test_resolving_twice_does_not_duplicate_audit_rows(self):
        self.client.post(reverse('discipline:resolve_case', args=[self.case.id]))
        count_after_first = DisciplineAuditLog.objects.filter(case=self.case, action='resolved').count()
        self.client.post(reverse('discipline:resolve_case', args=[self.case.id]))
        count_after_second = DisciplineAuditLog.objects.filter(case=self.case, action='resolved').count()

        self.case.refresh_from_db()
        self.assertEqual(self.case.status, 'resolved')
        self.assertEqual(count_after_first, count_after_second)

    def test_archiving_twice_does_not_duplicate_audit_rows(self):
        self.client.post(reverse('discipline:archive_case', args=[self.case.id]))
        count_after_first = DisciplineAuditLog.objects.filter(case=self.case, action='archived').count()
        self.client.post(reverse('discipline:archive_case', args=[self.case.id]))
        count_after_second = DisciplineAuditLog.objects.filter(case=self.case, action='archived').count()

        self.assertEqual(count_after_first, count_after_second)
