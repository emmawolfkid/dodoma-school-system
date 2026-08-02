from django.contrib import admin
from .models import User, Module, UserModule, StaffProfile


admin.site.register(User)
admin.site.register(Module)
admin.site.register(UserModule)


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'job_title', 'department', 'employment_status', 'employment_type', 'phone_number')
    list_filter = ('department', 'employment_status', 'employment_type')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'employee_id', 'job_title')