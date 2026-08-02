from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    path('', views.audit_dashboard, name='audit_home'),  # 🔥 FIX HERE
    path('dashboard/', views.audit_dashboard, name='audit_dashboard'),
    path('logs/', views.audit_logs, name='audit_logs'),
    path('export/pdf/', views.export_audit_pdf, name='export_audit_pdf'),
]