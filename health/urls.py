from django.urls import path
from . import views

app_name = 'health'

urlpatterns = [
    path('', views.health_dashboard, name='health_dashboard'),
    path('dashboard/', views.health_dashboard, name='health_dashboard_alt'),
    path('visits/', views.visit_list, name='visit_list'),
    path('visits/add/', views.add_visit, name='add_visit'),
    path('visits/add/<int:student_id>/', views.add_visit, name='add_visit_for_student'),
    path('student/<int:student_id>/', views.student_history, name='student_history'),
]
