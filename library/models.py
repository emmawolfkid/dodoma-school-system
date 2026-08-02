from django.conf import settings
from django.db import models
from django.utils.timezone import now


class Book(models.Model):
    CATEGORY_CHOICES = [
        ('textbook', 'Textbook'),
        ('reference', 'Reference'),
        ('fiction', 'Fiction'),
        ('non_fiction', 'Non-Fiction'),
        ('past_papers', 'Past Papers'),
        ('other', 'Other'),
    ]

    title = models.CharField(max_length=255, db_index=True)
    author = models.CharField(max_length=255, blank=True)
    isbn = models.CharField(max_length=30, blank=True, db_index=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='textbook')
    publisher = models.CharField(max_length=150, blank=True)
    edition = models.CharField(max_length=50, blank=True)
    shelf_location = models.CharField(max_length=50, blank=True)

    total_copies = models.PositiveIntegerField(default=1)
    available_copies = models.PositiveIntegerField(default=1)

    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['title']
        indexes = [
            models.Index(fields=['title'], name='lib_book_title_idx'),
            models.Index(fields=['category'], name='lib_book_category_idx'),
        ]

    def __str__(self):
        return f"{self.title} ({self.available_copies}/{self.total_copies} available)"

    @property
    def is_available(self):
        return self.available_copies > 0


class BorrowRecord(models.Model):
    STATUS_CHOICES = [
        ('borrowed', 'Borrowed'),
        ('returned', 'Returned'),
    ]

    book = models.ForeignKey(Book, on_delete=models.PROTECT, related_name='borrow_records')
    student = models.ForeignKey('registration.Student', on_delete=models.PROTECT, related_name='borrow_records')

    borrowed_date = models.DateField(default=now)
    due_date = models.DateField()
    returned_date = models.DateField(null=True, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='borrowed')

    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='books_issued')
    returned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='books_received')

    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-borrowed_date']
        indexes = [
            models.Index(fields=['status', 'due_date'], name='lib_borrow_status_due_idx'),
            models.Index(fields=['student', 'status'], name='lib_borrow_student_status_idx'),
        ]

    def __str__(self):
        return f"{self.book.title} -> {self.student}"

    @property
    def is_overdue(self):
        return self.status == 'borrowed' and self.due_date < now().date()
