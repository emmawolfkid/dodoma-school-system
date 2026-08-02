from django.urls import path
from . import views

app_name = 'certificate'

urlpatterns = [
    path('', views.certificate_dashboard, name='certificate_dashboard'),
    path('dashboard/', views.certificate_dashboard, name='certificate_dashboard_alt'),
    path('graduates/', views.graduates_list, name='graduates_list'),
    path('student/<int:student_id>/history/', views.student_full_history, name='student_full_history'),
    path('student/<int:student_id>/receipt/', views.generate_collection_receipt, name='generate_collection_receipt'),
    path('student/<int:student_id>/update-necta/', views.update_necta_details, name='update_necta_details'),
    path('student/<int:student_id>/mark-collection/', views.mark_collection, name='mark_collection'),
]