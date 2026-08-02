from django.test import TestCase
from django.urls import reverse

from accounts.models import User
from registration.models import Student

from .models import Book, BorrowRecord


def make_student(reg_no='LIB-STU-1'):
    return Student.objects.create(
        registration_number=reg_no, first_name='Test', last_name='Student',
        gender='Male', date_of_birth='2006-01-01', student_class='Form 1', section='A',
        date_of_admission='2022-01-01', region='X', district='X', ward='X', village='X',
        parent_name='X', parent_phone='0712345678', health_status='Fit',
    )


class BorrowReturnFlowTests(TestCase):
    def setUp(self):
        self.staff = User.objects.create_superuser(username='libstaff', password='StrongPass123', email='lib@example.com')
        self.book = Book.objects.create(title='Physics 101', total_copies=1, available_copies=1)
        self.student = make_student()
        self.client.force_login(self.staff)

    def test_borrowing_decrements_available_copies(self):
        self.client.post(reverse('library:borrow_book'), {
            'book_id': self.book.id, 'student_id': self.student.id, 'due_days': '14',
        })
        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 0)
        self.assertTrue(BorrowRecord.objects.filter(book=self.book, student=self.student, status='borrowed').exists())

    def test_cannot_borrow_when_no_copies_available(self):
        self.book.available_copies = 0
        self.book.save()
        self.client.post(reverse('library:borrow_book'), {
            'book_id': self.book.id, 'student_id': self.student.id, 'due_days': '14',
        })
        self.assertFalse(BorrowRecord.objects.filter(book=self.book, student=self.student).exists())

    def test_returning_increments_available_copies(self):
        record = BorrowRecord.objects.create(book=self.book, student=self.student, due_date='2099-01-01')
        self.book.available_copies = 0
        self.book.save()

        self.client.post(reverse('library:return_book', args=[record.id]))

        self.book.refresh_from_db()
        record.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)
        self.assertEqual(record.status, 'returned')

    def test_returning_twice_does_not_double_increment(self):
        record = BorrowRecord.objects.create(book=self.book, student=self.student, due_date='2099-01-01')
        self.book.available_copies = 0
        self.book.save()

        self.client.post(reverse('library:return_book', args=[record.id]))
        self.client.post(reverse('library:return_book', args=[record.id]))

        self.book.refresh_from_db()
        self.assertEqual(self.book.available_copies, 1)

    def test_non_staff_cannot_access_library(self):
        regular = User.objects.create_user(username='libregular', password='StrongPass123', is_approved=True)
        self.client.force_login(regular)
        response = self.client.get(reverse('library:library_dashboard'))
        self.assertEqual(response.status_code, 302)
