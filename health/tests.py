from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from registration.models import Student

from .models import HealthVisit


def make_student(reg_no='HEALTH-STU-1'):
    return Student.objects.create(
        registration_number=reg_no, first_name='Test', last_name='Student',
        gender='Male', date_of_birth='2006-01-01', student_class='Form 1', section='A',
        date_of_admission='2022-01-01', region='X', district='X', ward='X', village='X',
        parent_name='X', parent_phone='0712345678', health_status='Fit',
    )


class HealthVisitTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(username='healthstaff', password='StrongPass123', email='h@example.com')
        self.student = make_student()
        self.client.force_login(self.staff)

    def test_recording_visit_requires_reason(self):
        self.client.post(reverse('health:add_visit'), {'student_id': self.student.id, 'reason': ''})
        self.assertFalse(HealthVisit.objects.filter(student=self.student).exists())

    def test_recording_visit_success(self):
        response = self.client.post(reverse('health:add_visit'), {
            'student_id': self.student.id, 'reason': 'Fever', 'symptoms': 'High temperature',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(HealthVisit.objects.filter(student=self.student, reason='Fever').exists())

    def test_student_history_shows_visits(self):
        HealthVisit.objects.create(student=self.student, reason='Headache', recorded_by=self.staff)
        response = self.client.get(reverse('health:student_history', args=[self.student.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Headache')

    def test_non_staff_cannot_access_health_module(self):
        regular = User.objects.create_user(username='healthregular', password='StrongPass123', is_approved=True)
        self.client.force_login(regular)
        response = self.client.get(reverse('health:health_dashboard'))
        self.assertEqual(response.status_code, 302)
