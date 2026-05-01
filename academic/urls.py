from django.urls import path
from . import views

urlpatterns = [

    # DASHBOARD
    path('', views.academic_dashboard, name='academic_home'),  # This makes /academic/ work
    path('dashboard/', views.academic_dashboard, name='academic_dashboard'),

    # TEACHER
    path('subjects/', views.teacher_subjects, name='teacher_subjects'),
    path('select-exam/<int:subject_id>/<str:student_class>/', views.select_exam, name='select_exam'),
    path('enter-marks/<int:exam_id>/<int:subject_id>/<str:student_class>/', views.enter_marks, name='enter_marks'),
    path('upload-excel/<int:exam_id>/<int:subject_id>/<str:student_class>/', views.upload_marks_excel, name='upload_marks_excel'),

    # EXAMS
    path('exams/', views.exam_dashboard, name='exam_dashboard'),
    path('create-exam/', views.create_exam, name='create_exam'),
    path('toggle-lock/<int:exam_id>/', views.toggle_lock_exam, name='toggle_lock_exam'),
    path('generate/<int:exam_id>/', views.generate_results, name='generate_results'),
    path('publish/<int:exam_id>/', views.publish_results, name='publish_results'),

    # RESULTS
    path('class-results/<int:exam_id>/<str:student_class>/', views.class_results, name='class_results'),
    path('student-result/<int:exam_id>/<int:student_id>/', views.student_result_detail, name='student_result_detail'),

    # PDF
    path('pdf/student/<int:exam_id>/<int:student_id>/', views.download_student_pdf, name='download_student_pdf'),
    path('pdf/class/<int:exam_id>/<str:student_class>/', views.download_class_pdf, name='download_class_pdf'),

    # ADMIN USER MANAGEMENT (NEW 🔥)
    path('users/', views.academic_users, name='academic_users'),
    path('approve-user/<int:user_id>/', views.approve_academic_user, name='approve_academic_user'),
    path('assign-subjects/<int:user_id>/', views.assign_subjects, name='assign_subjects'),
    path('select-subjects/', views.select_subjects, name='select_subjects'),
path('approve-requests/', views.approve_subject_requests, name='approve_subject_requests'),
path('approve-request/<int:request_id>/', views.approve_request, name='approve_request'),
path('my-subjects/', views.manage_my_subjects, name='manage_my_subjects'),
path('remove-subject/<int:subject_id>/', views.remove_subject, name='remove_subject'),
path('admin-remove-subject/<int:id>/', views.admin_remove_subject, name='admin_remove_subject'),
path('reject-request/<int:request_id>/', views.reject_request, name='reject_request'),
path('exam/edit/<int:exam_id>/', views.create_exam, name='edit_exam'),
path('exam/delete/<int:exam_id>/', views.delete_exam, name='delete_exam'),
path('publish-results/<int:exam_id>/', views.publish_results, name='publish_results'),
# Add these lines to your urlpatterns:

# Admin results overview
path('admin-results/', views.admin_results_overview, name='admin_results_overview'),
path('admin-view-marks/<int:exam_id>/<str:student_class>/<int:subject_id>/', 
     views.admin_view_class_marks, name='admin_view_class_marks'),
     # Teacher-Subject Management
path('manage-teacher-subjects/', views.manage_teacher_subjects, name='manage_teacher_subjects'),
path('edit-teacher-assignment/<int:assignment_id>/', views.edit_teacher_assignment, name='edit_teacher_assignment'),
path('bulk-assign-subjects/', views.bulk_assign_subjects, name='bulk_assign_subjects'),
path('class-results-select/', views.select_class_results, name='select_class_results'),
path('class-results-view/', views.class_results_view, name='class_results_view'),
path('pdf/class/<int:exam_id>/', views.download_class_pdf, name='download_class_pdf'),
# Add this to urlpatterns
path('clear-marks/<int:exam_id>/<int:subject_id>/<str:student_class>/', views.clear_subject_marks, name='clear_subject_marks'),
path(
    'unlock-marks/<int:exam_id>/<int:subject_id>/<str:student_class>/',
    views.unlock_marks,
    name='unlock_marks'
),
path('exam/<int:exam_id>/unpublish/', views.unpublish_results, name='unpublish_results'),
]