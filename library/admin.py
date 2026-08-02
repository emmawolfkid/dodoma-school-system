from django.contrib import admin
from .models import Book, BorrowRecord


@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'category', 'total_copies', 'available_copies', 'shelf_location')
    list_filter = ('category',)
    search_fields = ('title', 'author', 'isbn')


@admin.register(BorrowRecord)
class BorrowRecordAdmin(admin.ModelAdmin):
    list_display = ('book', 'student', 'borrowed_date', 'due_date', 'returned_date', 'status')
    list_filter = ('status',)
    search_fields = ('book__title', 'student__first_name', 'student__last_name', 'student__registration_number')
