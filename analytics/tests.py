from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from registration.models import Student
from library.models import Book


class AnalyticsAccessTests(TestCase):
    def test_non_superuser_cannot_access(self):
        regular = User.objects.create_user(username='an_regular', password='StrongPass123', is_approved=True)
        self.client.force_login(regular)
        response = self.client.get(reverse('analytics:analytics_dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_superuser_can_access(self):
        su = User.objects.create_superuser(username='an_root', password='StrongPass123', email='r@example.com')
        self.client.force_login(su)
        response = self.client.get(reverse('analytics:analytics_dashboard'))
        self.assertEqual(response.status_code, 200)


class AnalyticsDataTests(TestCase):
    def setUp(self):
        self.su = User.objects.create_superuser(username='an_root2', password='StrongPass123', email='r2@example.com')
        self.client.force_login(self.su)

    def test_reflects_actual_counts(self):
        Student.objects.create(
            registration_number='AN-DATA-1', first_name='A', last_name='B', gender='Male',
            date_of_birth='2006-01-01', student_class='Form 3', section='A',
            date_of_admission='2022-01-01', region='X', district='X', ward='X', village='X',
            parent_name='X', parent_phone='0712345678', health_status='Fit', school_status='Active',
        )
        Book.objects.create(title='Test Book', total_copies=1, available_copies=1)

        response = self.client.get(reverse('analytics:analytics_dashboard'))
        self.assertEqual(response.context['total_active'], 1)
        self.assertEqual(response.context['total_books'], 1)
