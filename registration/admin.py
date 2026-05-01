from django.contrib import admin
from .models import Student, Equipment


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('registration_number', 'first_name', 'student_class', 'school_status')
    search_fields = ('first_name', 'registration_number')
    list_filter = ('student_class', 'school_status', 'gender')


@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('name',)