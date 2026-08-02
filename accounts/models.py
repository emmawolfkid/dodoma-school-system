from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    is_approved = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=False)

    def __str__(self):
        return self.username
    
class StaffProfile(models.Model):
    """
    HR record for a staff member -- distinct from UserModule (which only
    tracks per-module permissions). One row per User who is actual school
    staff (not every login necessarily needs one, but every teacher/admin
    should).
    """

    EMPLOYMENT_TYPE_CHOICES = [
        ('permanent', 'Permanent'),
        ('contract', 'Contract'),
        ('part_time', 'Part-Time'),
        ('volunteer', 'Volunteer'),
    ]

    EMPLOYMENT_STATUS_CHOICES = [
        ('active', 'Active'),
        ('on_leave', 'On Leave'),
        ('suspended', 'Suspended'),
        ('resigned', 'Resigned'),
        ('terminated', 'Terminated'),
    ]

    GENDER_CHOICES = [
        ('Male', 'Male'),
        ('Female', 'Female'),
    ]

    DEPARTMENT_CHOICES = [
        ('academic', 'Academic'),
        ('administration', 'Administration'),
        ('discipline', 'Discipline'),
        ('registration', 'Registration'),
        ('certificate', 'Certificate / Examinations'),
        ('support', 'Support Staff'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')

    employee_id = models.CharField(max_length=50, unique=True, blank=True, null=True)
    national_id = models.CharField(max_length=50, blank=True, help_text="NIDA number")

    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, blank=True)

    job_title = models.CharField(max_length=100, blank=True, help_text="e.g. Mathematics Teacher, Bursar, Discipline Master")
    department = models.CharField(max_length=20, choices=DEPARTMENT_CHOICES, blank=True)
    qualification = models.CharField(max_length=255, blank=True, help_text="e.g. Diploma in Education, BSc Mathematics")

    date_employed = models.DateField(null=True, blank=True)
    employment_type = models.CharField(max_length=20, choices=EMPLOYMENT_TYPE_CHOICES, default='permanent')
    employment_status = models.CharField(max_length=20, choices=EMPLOYMENT_STATUS_CHOICES, default='active')

    region = models.CharField(max_length=100, blank=True)
    district = models.CharField(max_length=100, blank=True)
    address = models.CharField(max_length=255, blank=True)

    emergency_contact_name = models.CharField(max_length=100, blank=True)
    emergency_contact_phone = models.CharField(max_length=20, blank=True)

    profile_photo = models.ImageField(upload_to='staff/', blank=True, null=True)

    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=['department', 'employment_status'], name='acct_staff_dept_status_idx'),
            models.Index(fields=['employment_status'], name='acct_staff_status_idx'),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.job_title or 'Staff'})"


class Module(models.Model):
    name = models.CharField(max_length=100, unique=True)

    def save(self, *args, **kwargs):
        self.name = self.name.lower()   # enforce lowercase
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class UserModule(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    module = models.ForeignKey(Module, on_delete=models.CASCADE)

    is_admin = models.BooleanField(default=False)

    can_add = models.BooleanField(default=False)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)
    can_view = models.BooleanField(default=True)
    is_exam_coordinator = models.BooleanField(default=False)

    is_approved = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} - {self.module.name}"
