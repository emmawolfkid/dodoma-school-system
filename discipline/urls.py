from django.urls import path
from . import views

app_name = 'discipline'

urlpatterns = [
    path('', views.discipline_dashboard, name='dashboard'),
    path('dashboard/', views.discipline_dashboard, name='dashboard_alt'),
    path('student/<int:student_id>/', views.student_discipline_profile, name='student_profile'),
    path('student/<int:student_id>/add-case/', views.add_case, name='add_case'),
    path('cases/', views.all_cases, name='all_cases'),
    path('students/', views.class_list, name='class_list'),
    path('students/<str:class_name>/', views.students_by_class, name='students_by_class'),
    path('report/student/<int:student_id>/', views.student_report, name='student_report'),
    path('report/all/', views.all_cases_report, name='all_cases_report'),
    path('case/<int:case_id>/return/', views.mark_returned, name='mark_returned'),
    path('case/<int:case_id>/edit/', views.edit_case, name='edit_case'),
    path('cases/<int:case_id>/restore/', views.restore_case, name='restore_case'),
    path('cases/<int:case_id>/archive/', views.archive_case, name='archive_case'),
    path('case/<int:case_id>/resolve/', views.resolve_case, name='resolve_case'),
]