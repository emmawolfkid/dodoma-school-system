from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import render, redirect, get_object_or_404
from django.utils.timezone import now

from accounts.models import UserModule
from registration.models import Student
from audit.services import log_action

from .models import Book, BorrowRecord


def has_library_access(user):
    if user.is_superuser:
        return True
    return UserModule.objects.filter(user=user, module__name='library', is_approved=True).exists()


@login_required
def library_dashboard(request):
    if not has_library_access(request.user):
        messages.error(request, "Access denied. You do not have access to the Library module.")
        return redirect('dashboard')

    total_books = Book.objects.count()
    total_copies = sum(Book.objects.values_list('total_copies', flat=True))
    borrowed_count = BorrowRecord.objects.filter(status='borrowed').count()
    overdue_count = BorrowRecord.objects.filter(status='borrowed', due_date__lt=now().date()).count()

    recent_borrows = BorrowRecord.objects.select_related('book', 'student').order_by('-borrowed_date')[:8]

    return render(request, 'library/dashboard.html', {
        'total_books': total_books,
        'total_copies': total_copies,
        'borrowed_count': borrowed_count,
        'overdue_count': overdue_count,
        'recent_borrows': recent_borrows,
    })


@login_required
def book_list(request):
    if not has_library_access(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    query = request.GET.get('q', '').strip()
    category = request.GET.get('category', '').strip()

    books = Book.objects.all()
    if query:
        books = books.filter(
            Q(title__icontains=query) | Q(author__icontains=query) | Q(isbn__icontains=query)
        )
    if category:
        books = books.filter(category=category)

    paginator = Paginator(books, 20)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'library/book_list.html', {
        'page_obj': page_obj,
        'query': query,
        'category': category,
        'category_choices': Book.CATEGORY_CHOICES,
    })


@login_required
def add_book(request):
    if not has_library_access(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        if not title:
            messages.error(request, "Title is required.")
            return redirect('library:add_book')

        total_copies = int(request.POST.get('total_copies') or 1)

        book = Book.objects.create(
            title=title,
            author=request.POST.get('author', '').strip(),
            isbn=request.POST.get('isbn', '').strip(),
            category=request.POST.get('category', 'textbook'),
            publisher=request.POST.get('publisher', '').strip(),
            edition=request.POST.get('edition', '').strip(),
            shelf_location=request.POST.get('shelf_location', '').strip(),
            total_copies=total_copies,
            available_copies=total_copies,
        )

        log_action(user=request.user, action='create', instance=book, module='library', changes={'title': book.title})

        messages.success(request, f"'{book.title}' added to the library.")
        return redirect('library:book_list')

    return render(request, 'library/add_book.html', {'category_choices': Book.CATEGORY_CHOICES})


@login_required
def edit_book(request, book_id):
    if not has_library_access(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    book = get_object_or_404(Book, id=book_id)

    if request.method == 'POST':
        new_total = int(request.POST.get('total_copies') or book.total_copies)
        borrowed_out = book.total_copies - book.available_copies
        if new_total < borrowed_out:
            messages.error(request, f"Cannot set total copies below {borrowed_out} -- that many are currently borrowed out.")
            return redirect('library:edit_book', book_id=book.id)

        book.title = request.POST.get('title', '').strip() or book.title
        book.author = request.POST.get('author', '').strip()
        book.isbn = request.POST.get('isbn', '').strip()
        book.category = request.POST.get('category', book.category)
        book.publisher = request.POST.get('publisher', '').strip()
        book.edition = request.POST.get('edition', '').strip()
        book.shelf_location = request.POST.get('shelf_location', '').strip()
        book.available_copies = new_total - borrowed_out
        book.total_copies = new_total
        book.save()

        log_action(user=request.user, action='update', instance=book, module='library', changes={'title': book.title})

        messages.success(request, f"'{book.title}' updated.")
        return redirect('library:book_list')

    return render(request, 'library/edit_book.html', {'book': book, 'category_choices': Book.CATEGORY_CHOICES})


@login_required
def borrow_records(request):
    if not has_library_access(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    status = request.GET.get('status', '').strip()
    records = BorrowRecord.objects.select_related('book', 'student').order_by('-borrowed_date')

    if status == 'overdue':
        records = records.filter(status='borrowed', due_date__lt=now().date())
    elif status:
        records = records.filter(status=status)

    paginator = Paginator(records, 25)
    page_obj = paginator.get_page(request.GET.get('page', 1))

    return render(request, 'library/borrow_records.html', {
        'page_obj': page_obj,
        'status': status,
    })


@login_required
def borrow_book(request):
    if not has_library_access(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    if request.method == 'POST':
        student = get_object_or_404(Student, id=request.POST.get('student_id'), is_archived=False)
        due_days = int(request.POST.get('due_days') or 14)

        with transaction.atomic():
            book = get_object_or_404(Book.objects.select_for_update(), id=request.POST.get('book_id'))

            if not book.is_available:
                messages.error(request, f"No available copies of '{book.title}' to lend out.")
                return redirect('library:book_list')

            book.available_copies -= 1
            book.save(update_fields=['available_copies'])

            record = BorrowRecord.objects.create(
                book=book,
                student=student,
                due_date=now().date() + timedelta(days=due_days),
                issued_by=request.user,
            )

        log_action(
            user=request.user, action='create', instance=record, module='library',
            changes={'book': book.title, 'student': str(student)}
        )

        messages.success(request, f"'{book.title}' issued to {student} (due back {record.due_date}).")
        return redirect('library:borrow_records')

    students = Student.objects.filter(is_archived=False, school_status='Active').order_by('first_name')
    available_books = Book.objects.filter(available_copies__gt=0)
    return render(request, 'library/borrow_book.html', {'students': students, 'books': available_books})


@login_required
def return_book(request, record_id):
    if not has_library_access(request.user):
        messages.error(request, "Access denied.")
        return redirect('dashboard')

    if request.method != 'POST':
        messages.error(request, "Return must be confirmed from the borrow records list.")
        return redirect('library:borrow_records')

    record = get_object_or_404(BorrowRecord, id=record_id)

    if record.status == 'returned':
        messages.info(request, "This book was already marked returned.")
        return redirect('library:borrow_records')

    record.status = 'returned'
    record.returned_date = now().date()
    record.returned_to = request.user
    record.save()

    record.book.available_copies += 1
    record.book.save(update_fields=['available_copies'])

    log_action(
        user=request.user, action='update', instance=record, module='library',
        changes={'event': 'book_returned', 'book': record.book.title, 'student': str(record.student)}
    )

    messages.success(request, f"'{record.book.title}' marked returned.")
    return redirect('library:borrow_records')
