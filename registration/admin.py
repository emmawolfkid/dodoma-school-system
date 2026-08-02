from django.contrib import admin
from django.urls import path
from django.shortcuts import redirect
from .models import Student, Equipment


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('registration_number', 'first_name', 'last_name', 'student_class', 'section', 'school_status')
    list_filter = ('student_class', 'school_status', 'gender')
    search_fields = ('registration_number', 'first_name', 'last_name', 'parent_phone')
    ordering = ('student_class', 'first_name')
    change_list_template = "registration/admin/student_changelist.html"

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('promote-students-redirect/', self.admin_site.admin_view(self.promote_redirect), name='promote_redirect'),
        ]
        return custom_urls + urls

    def promote_redirect(self, request):
        """Only Superusers can initiate promotion from here."""
        if not request.user.is_superuser:
            from django.contrib import messages
            messages.error(request, "Only System Admin can initiate promotion from here.")
            return redirect('admin:registration_student_changelist')
        return redirect('promote_students')

@admin.register(Equipment)
class EquipmentAdmin(admin.ModelAdmin):
    list_display = ('name',)