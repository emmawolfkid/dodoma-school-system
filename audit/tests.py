from django.contrib.auth.models import AnonymousUser
from django.test import TestCase

from accounts.models import User, Module, UserModule
from registration.models import Student
from .admin import has_audit_access, AuditLogAdmin
from .middleware import get_current_user, _user
from .models import AuditLog


class HasAuditAccessTests(TestCase):
    def test_anonymous_user_does_not_crash_and_returns_false(self):
        """
        Regression test: has_audit_access() used to filter UserModule by
        request.user without checking authentication, which raised a
        TypeError for AnonymousUser -- crashing the Django admin *login
        page itself* for anyone not yet logged in.
        """
        self.assertFalse(has_audit_access(AnonymousUser()))

    def test_approved_audit_user_has_access(self):
        module, _ = Module.objects.get_or_create(name='audit')
        user = User.objects.create_user(username='auditor', password='StrongPass123', is_approved=True)
        UserModule.objects.create(user=user, module=module, is_approved=True)
        self.assertTrue(has_audit_access(user))

    def test_unapproved_user_has_no_access(self):
        user = User.objects.create_user(username='rando', password='StrongPass123', is_approved=True)
        self.assertFalse(has_audit_access(user))


class AuditLogAdminImmutabilityTests(TestCase):
    def setUp(self):
        self.admin = AuditLogAdmin(AuditLog, None)

    def test_cannot_add_change_or_delete(self):
        self.assertFalse(self.admin.has_add_permission(None))
        self.assertFalse(self.admin.has_change_permission(None))
        self.assertFalse(self.admin.has_delete_permission(None))


class CurrentUserMiddlewareTests(TestCase):
    def tearDown(self):
        _user.value = None

    def test_get_current_user_defaults_to_none(self):
        _user.value = None
        self.assertIsNone(get_current_user())

    def test_get_current_user_returns_none_for_anonymous(self):
        _user.value = AnonymousUser()
        self.assertIsNone(get_current_user())

    def test_get_current_user_returns_authenticated_user(self):
        user = User.objects.create_user(username='someone', password='StrongPass123')
        _user.value = user
        self.assertEqual(get_current_user(), user)


class AuditSignalCapturesRealUserTests(TestCase):
    """
    Regression test: audit/signals.py used to hardcode user=None on every
    model-level audit entry (Student/DisciplineCase/StudentMark changes),
    so the audit trail always showed "System" instead of the real actor.
    """

    def test_student_create_logs_current_user_not_none(self):
        actor = User.objects.create_user(username='registrar', password='StrongPass123')
        _user.value = actor
        try:
            Student.objects.create(
                registration_number='TEST-AUDIT-1', first_name='A', last_name='B',
                gender='Male', date_of_birth='2005-01-01', student_class='Form 1', section='A',
                date_of_admission='2020-01-01', region='X', district='X', ward='X', village='X',
                parent_name='X', parent_phone='0712345678', health_status='Fit',
            )
        finally:
            _user.value = None

        log = AuditLog.objects.filter(module='registration', action='create').latest('timestamp')
        self.assertEqual(log.user, actor)
