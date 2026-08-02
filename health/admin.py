from django.contrib import admin
from .models import HealthVisit


@admin.register(HealthVisit)
class HealthVisitAdmin(admin.ModelAdmin):
    list_display = ('student', 'reason', 'visit_date', 'referred_to_hospital', 'follow_up_required')
    list_filter = ('referred_to_hospital', 'follow_up_required')
    search_fields = ('student__first_name', 'student__last_name', 'student__registration_number', 'reason')
