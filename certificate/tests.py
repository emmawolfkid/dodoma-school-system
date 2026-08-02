from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from registration.models import Student

from .models import GraduateCollection


def make_graduate(reg_no='GRAD-1'):
    return Student.objects.create(
        registration_number=reg_no, first_name='Test', last_name='Graduate',
        gender='Male', date_of_birth='2004-01-01', student_class='Form 6', section='PCM',
        date_of_admission='2020-01-01', region='X', district='X', ward='X', village='X',
        parent_name='X', parent_phone='0712345678', health_status='Fit',
        school_status='Graduated',
    )


class MarkCollectionTests(TestCase):
    """Regression test: mark_collection could silently overwrite an
    existing collection (re-issuing a certificate already collected,
    with no record of the original issuance)."""

    def setUp(self):
        self.staff = User.objects.create_user(username='certstaff', password='StrongPass123', is_approved=True, is_superuser=True)
        self.student = make_graduate()
        self.collection = GraduateCollection.objects.create(
            student=self.student,
            necta_certificate_no='CERT-001',
            certificate_received_at_school=True,
        )
        self.client.force_login(self.staff)

    def test_first_collection_succeeds(self):
        response = self.client.post(
            reverse('certificate:mark_collection', args=[self.student.id]),
            {'type': 'cert'},
        )
        self.assertEqual(response.status_code, 302)
        self.collection.refresh_from_db()
        self.assertTrue(self.collection.certificate_collected)
        first_issued_by = self.collection.issued_by

        # Second attempt must be blocked, not silently re-issue.
        other_staff = User.objects.create_user(username='certstaff2', password='StrongPass123', is_approved=True, is_superuser=True)
        self.client.logout()
        self.client.force_login(other_staff)
        self.client.post(reverse('certificate:mark_collection', args=[self.student.id]), {'type': 'cert'})

        self.collection.refresh_from_db()
        self.assertEqual(self.collection.issued_by, first_issued_by)


class GenerateReceiptStatusTests(TestCase):
    """Regression test: generate_collection_receipt didn't require
    school_status='Graduated', letting staff generate a graduation
    receipt for a student who hadn't graduated."""

    def setUp(self):
        self.staff = User.objects.create_user(username='certstaff3', password='StrongPass123', is_approved=True, is_superuser=True)
        self.client.force_login(self.staff)

    def test_non_graduated_student_receipt_blocked(self):
        active_student = Student.objects.create(
            registration_number='ACTIVE-1', first_name='Active', last_name='Student',
            gender='Male', date_of_birth='2008-01-01', student_class='Form 2', section='A',
            date_of_admission='2023-01-01', region='X', district='X', ward='X', village='X',
            parent_name='X', parent_phone='0712345678', health_status='Fit',
            school_status='Active',
        )
        response = self.client.get(reverse('certificate:generate_collection_receipt', args=[active_student.id]))
        self.assertEqual(response.status_code, 404)

    def test_graduated_student_receipt_allowed(self):
        graduate = make_graduate('GRAD-2')
        response = self.client.get(reverse('certificate:generate_collection_receipt', args=[graduate.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get('Content-Type'), 'application/pdf')
