from django.urls import path
from . import views

app_name = 'library'

urlpatterns = [
    path('', views.library_dashboard, name='library_dashboard'),
    path('dashboard/', views.library_dashboard, name='library_dashboard_alt'),
    path('books/', views.book_list, name='book_list'),
    path('books/add/', views.add_book, name='add_book'),
    path('books/<int:book_id>/edit/', views.edit_book, name='edit_book'),
    path('borrow/', views.borrow_book, name='borrow_book'),
    path('records/', views.borrow_records, name='borrow_records'),
    path('records/<int:record_id>/return/', views.return_book, name='return_book'),
]
