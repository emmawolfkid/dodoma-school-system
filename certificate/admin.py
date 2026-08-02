from django.contrib import admin
from .models import GraduateCollection

@admin.register(GraduateCollection)
class GraduateCollectionAdmin(admin.ModelAdmin):
    list_display = (
        'student',
        'certificate_received_at_school',
        'result_slip_received_at_school',
        'certificate_collected',
        'result_slip_collected',
        'date_issued',
        'issued_by',
    )
    list_filter = (
        'certificate_received_at_school',
        'result_slip_received_at_school',
        'certificate_collected',
        'result_slip_collected',
        'date_issued',
    )
    search_fields = ('student__registration_number', 'student__first_name', 'student__last_name')
    raw_id_fields = ('student',)
    ordering = ('-date_issued',)
