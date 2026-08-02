from django.test import TestCase
from django.urls import reverse

from accounts.models import User, Module, UserModule

from .forms import StudentForm
from .models import Student
from .utils import has_permission


def make_student(reg_no='STU-1', **overrides):
    data = dict(
        registration_number=reg_no, first_name='Test', last_name='Student',
        gender='Male', date_of_birth='2006-01-01', student_class='Form 1', section='A',
        date_of_admission='2022-01-01', region='X', district='X', ward='X', village='X',
        parent_name='X', parent_phone='0712345678', health_status='Fit',
    )
    data.update(overrides)
    return Student.objects.create(**data)


class StudentFormFieldTests(TestCase):
    def test_form_excludes_archive_fields(self):
        """
        Regression test: StudentForm used fields = '__all__', which let a
        plain 'edit'-permission user archive a student by just posting
        is_archived=on through the normal edit form.
        """
        form = StudentForm()
        self.assertNotIn('is_archived', form.fields)
        self.assertNotIn('archived_at', form.fields)

    def test_form_still_allows_class_and_status_changes(self):
        """student_class/school_status are intentionally still editable --
        edit_student() uses changes to those fields to record manual
        promotion/graduation history."""
        form = StudentForm()
        self.assertIn('student_class', form.fields)
        self.assertIn('school_status', form.fields)


class PhoneValidationTests(TestCase):
    def _valid_data(self, **overrides):
        data = dict(
            registration_number='PH-1', first_name='A', last_name='B', gender='Male',
            date_of_birth='2006-01-01', student_class='Form 1', section='A',
            date_of_admission='2022-01-01', region='X', district='X', ward='X', village='X',
            parent_name='X', parent_phone='0712345678', health_status='Fit',
        )
        data.update(overrides)
        return data

    def test_valid_tanzanian_phone_accepted(self):
        form = StudentForm(data=self._valid_data())
        form.is_valid()
        self.assertNotIn('parent_phone', form.errors)

    def test_invalid_phone_rejected(self):
        form = StudentForm(data=self._valid_data(parent_phone='123'))
        self.assertFalse(form.is_valid())
        self.assertIn('parent_phone', form.errors)

    def test_optional_phone_blank_is_allowed(self):
        form = StudentForm(data=self._valid_data(parent_phone2=''))
        form.is_valid()
        self.assertNotIn('parent_phone2', form.errors)


class RestoreStudentTests(TestCase):
    def setUp(self):
        self.module, _ = Module.objects.get_or_create(name='registration')
        self.admin = User.objects.create_user(username='regadmin', password='StrongPass123', is_approved=True)
        UserModule.objects.create(
            user=self.admin, module=self.module, is_admin=True, is_approved=True,
            can_add=True, can_edit=True, can_delete=True,
        )
        self.student = make_student('RESTORE-1')
        self.student.archive()

    def test_restore_requires_post(self):
        """Regression test: restore_student had no method guard -- a GET
        request (e.g. a forced <img> link) would silently un-archive a
        student with no CSRF protection."""
        self.client.force_login(self.admin)
        response = self.client.get(reverse('restore_student', args=[self.student.id]))
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_archived)
        self.assertEqual(response.status_code, 302)

    def test_restore_via_post_works(self):
        self.client.force_login(self.admin)
        self.client.post(reverse('restore_student', args=[self.student.id]))
        self.student.refresh_from_db()
        self.assertFalse(self.student.is_archived)


class HasPermissionSingleSourceTests(TestCase):
    """Regression test: registration/views.py used to define its own copy
    of has_permission(), duplicating registration/utils.py's version."""

    def test_views_imports_from_utils(self):
        from . import views
        self.assertIs(views.has_permission, has_permission)

    def test_superuser_has_all_permissions(self):
        su = User.objects.create_superuser(username='root', password='StrongPass123', email='root@example.com')
        self.assertTrue(has_permission(su, 'add'))
        self.assertTrue(has_permission(su, 'delete'))
