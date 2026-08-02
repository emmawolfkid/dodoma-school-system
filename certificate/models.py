from django.db import models
from django.conf import settings
from registration.models import Student

class GraduateCollection(models.Model):
    # PROTECT so an accidental Student hard-delete can't silently wipe the
    # official NECTA certificate/result-slip collection record.
    student = models.OneToOneField(Student, on_delete=models.PROTECT, related_name='collection_record')
    
    # NECTA Document Details
    necta_certificate_no = models.CharField(max_length=100, blank=True, null=True, help_text="Official NECTA Certificate Number")
    necta_result_slip_no = models.CharField(max_length=100, blank=True, null=True, help_text="Official NECTA Result Slip Number")
    
    # Reception at School
    is_received_at_school = models.BooleanField(default=False, help_text="Mark True when the batch arrives from NECTA")
    certificate_received_at_school = models.BooleanField(default=False)
    result_slip_received_at_school = models.BooleanField(default=False)
    certificate_unavailable_reason = models.CharField(max_length=255, blank=True)
    result_slip_unavailable_reason = models.CharField(max_length=255, blank=True)
    
    # Collection by Student
    certificate_collected = models.BooleanField(default=False, verbose_name="Collected by Student")
    result_slip_collected = models.BooleanField(default=False, verbose_name="Collected by Student")
    
    date_issued = models.DateTimeField(null=True, blank=True)
    issued_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Collection for {self.student.registration_number}"

    @property
    def status(self):
        if self.certificate_collected and self.result_slip_collected:
            return "Both Collected"
        if self.certificate_collected:
            return "Certificate Only"
        if self.result_slip_collected:
            return "Result Slip Only"
        return "Not Collected"

    @property
    def certificate_available(self):
        return self.certificate_received_at_school and bool(self.necta_certificate_no)

    @property
    def result_slip_available(self):
        return self.result_slip_received_at_school and bool(self.necta_result_slip_no)

    class Meta:
        indexes = [
            models.Index(fields=['certificate_collected', 'result_slip_collected'], name='cert_collection_status_idx'),
            models.Index(fields=['certificate_received_at_school', 'result_slip_received_at_school'], name='cert_received_status_idx'),
        ]
