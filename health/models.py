from django.conf import settings
from django.db import models
from django.utils.timezone import now


class HealthVisit(models.Model):
    """A single nurse/sick-bay visit record for a student."""

    student = models.ForeignKey('registration.Student', on_delete=models.PROTECT, related_name='health_visits')

    visit_date = models.DateTimeField(default=now)
    reason = models.CharField(max_length=255, help_text="e.g. Headache, Fever, Injury")
    symptoms = models.TextField(blank=True)
    treatment_given = models.TextField(blank=True)

    referred_to_hospital = models.BooleanField(default=False)
    follow_up_required = models.BooleanField(default=False)
    follow_up_date = models.DateField(null=True, blank=True)

    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-visit_date']
        indexes = [
            models.Index(fields=['student', 'visit_date'], name='health_visit_student_date_idx'),
            models.Index(fields=['follow_up_required', 'follow_up_date'], name='health_visit_followup_idx'),
        ]

    def __str__(self):
        return f"{self.student} - {self.reason} ({self.visit_date.date()})"
