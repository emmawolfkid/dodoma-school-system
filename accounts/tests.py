from django.test import TestCase
from django.urls import reverse

from audit.models import AuditLog
from .models import User, Module, UserModule, StaffProfile


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='teacher1', password='StrongPass123', email='teacher1@example.com',
            is_approved=True,
        )
        self.user.is_superuser = True  # bypasses the "needs an approved module" gate
        self.user.save()

    def test_login_success_logs_audit_entry(self):
        response = self.client.post(reverse('login'), {'username': 'teacher1', 'password': 'StrongPass123'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AuditLog.objects.filter(user=self.user, action='login', changes__status='success').exists())

    def test_login_failure_does_not_crash_and_logs_attempt(self):
        response = self.client.post(reverse('login'), {'username': 'teacher1', 'password': 'WrongPassword'})
        self.assertEqual(response.status_code, 200)  # re-renders login form with an error, no redirect
        self.assertTrue(AuditLog.objects.filter(action='login', changes__status='failed').exists())

    def test_unapproved_account_cannot_login(self):
        User.objects.create_user(username='pending_user', password='StrongPass123', is_approved=False)
        response = self.client.post(reverse('login'), {'username': 'pending_user', 'password': 'StrongPass123'})
        self.assertEqual(response.status_code, 302)
        # Should redirect back to login, not establish a session
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_logout_requires_authentication_and_does_not_crash(self):
        """
        Regression test: logout_view used to crash with a ValueError when
        called by an unauthenticated/expired session because it wrote
        AuditLog(user=AnonymousUser) before checking auth.
        """
        response = self.client.get(reverse('logout'))
        # login_required should redirect to the login page instead of 500ing
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse('login'), response.url)

    def test_logout_while_authenticated_logs_entry_and_ends_session(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('logout'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue(AuditLog.objects.filter(user=self.user, action='logout').exists())
        self.assertNotIn('_auth_user_id', self.client.session)


class SignupNotificationTests(TestCase):
    def test_signup_creates_pending_usermodule_and_notifies_admins(self):
        module, _ = Module.objects.get_or_create(name='registration')
        admin_user = User.objects.create_user(
            username='reg_admin', password='StrongPass123', email='admin@example.com', is_approved=True
        )
        UserModule.objects.create(user=admin_user, module=module, is_admin=True, is_approved=True)

        response = self.client.post(reverse('signup'), {
            'username': 'newteacher',
            'email': 'newteacher@example.com',
            'password1': 'ComplexPass123!',
            'password2': 'ComplexPass123!',
            'modules': [module.id],
        })
        self.assertEqual(response.status_code, 302)

        new_user = User.objects.get(username='newteacher')
        self.assertFalse(new_user.is_approved)
        self.assertTrue(UserModule.objects.filter(user=new_user, module=module, is_approved=False).exists())

        # The admin should have gotten an in-app notification about it.
        from academic.models import Notification
        self.assertTrue(
            Notification.objects.filter(user=admin_user, message__icontains='newteacher').exists()
        )


class AdminForceResetTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(username='root', password='StrongPass123', email='root@example.com')
        self.target = User.objects.create_user(username='target', password='OldPass123', is_approved=True)

    def test_requires_post(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('admin_force_reset', args=[self.target.id]))
        self.target.refresh_from_db()
        self.assertFalse(self.target.must_change_password)
        self.assertEqual(response.status_code, 302)

    def test_post_forces_password_change(self):
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('admin_force_reset', args=[self.target.id]))
        self.target.refresh_from_db()
        self.assertTrue(self.target.must_change_password)
        self.assertEqual(response.status_code, 302)

    def test_non_superuser_cannot_force_reset(self):
        regular = User.objects.create_user(username='regular', password='StrongPass123', is_approved=True)
        self.client.force_login(regular)
        self.client.post(reverse('admin_force_reset', args=[self.target.id]))
        self.target.refresh_from_db()
        self.assertFalse(self.target.must_change_password)


class StaffDirectoryTests(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(username='root2', password='StrongPass123', email='root2@example.com')
        self.teacher = User.objects.create_user(
            username='mrsmith', password='StrongPass123', is_approved=True,
            first_name='John', last_name='Smith',
        )

    def test_non_superuser_cannot_view_directory(self):
        regular = User.objects.create_user(username='regular2', password='StrongPass123', is_approved=True)
        self.client.force_login(regular)
        response = self.client.get(reverse('staff_directory'))
        self.assertEqual(response.status_code, 302)

    def test_superuser_can_view_directory(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('staff_directory'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'John')

    def test_creating_staff_profile_via_edit_view(self):
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('edit_staff_profile', args=[self.teacher.id]), {
            'employee_id': 'EMP-001',
            'job_title': 'Mathematics Teacher',
            'department': 'academic',
            'employment_type': 'permanent',
            'employment_status': 'active',
            'gender': 'Male',
            'national_id': '',
            'phone_number': '0712345678',
            'qualification': 'BSc Mathematics',
            'region': '', 'district': '', 'address': '',
            'emergency_contact_name': '', 'emergency_contact_phone': '',
            'notes': '',
        })
        self.assertEqual(response.status_code, 302)
        profile = StaffProfile.objects.get(user=self.teacher)
        self.assertEqual(profile.job_title, 'Mathematics Teacher')
        self.assertEqual(profile.employee_id, 'EMP-001')
