from django.db import models
from django.conf import settings
from django.utils.timezone import now


# =========================================
# 🔷 DISCIPLINE CASE
# =========================================
class DisciplineCase(models.Model):

    CASE_TYPE_CHOICES = (
        ('minor', 'Minor'),
        ('major', 'Major'),
    )

    STATUS_CHOICES = (
        ('open', 'Open'),
        ('resolved', 'Resolved'),
    )

    ACTION_TYPE_CHOICES = (
        ('warning', 'Warning'),
        ('punishment', 'Punishment'),
        ('suspension', 'Suspension'),
    )

    student = models.ForeignKey(
        'registration.Student',
        # Discipline history must survive a Student row being removed —
        # archive the student instead of deleting; PROTECT stops an
        # accidental hard-delete from silently wiping their case history.
        on_delete=models.PROTECT,
        related_name='discipline_cases',
        db_index=True
    )

    reported_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='reported_cases',
        db_index=True
    )

    case_type = models.CharField(
        max_length=10,
        choices=CASE_TYPE_CHOICES,
        db_index=True
    )

    title = models.CharField(max_length=255, db_index=True)

    description = models.TextField()

    # 🔥 FIX: ADD DEFAULT (SOLVES MIGRATION ERROR)
    action_type = models.CharField(
        max_length=20,
        choices=ACTION_TYPE_CHOICES,
        default='warning',
        db_index=True
    )

    action_taken = models.TextField(blank=True, null=True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='open',
        db_index=True
    )

    severity_points = models.PositiveIntegerField(default=0)

    date_of_incident = models.DateField(db_index=True)
    date_reported = models.DateTimeField(auto_now_add=True, db_index=True)
    date_updated = models.DateTimeField(auto_now=True)

    is_archived = models.BooleanField(default=False, db_index=True)

    def save(self, *args, **kwargs):
        # 🔥 AUTO SET ACTION TAKEN
        if self.action_type and not self.action_taken:
            self.action_taken = self.action_type.capitalize()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student.registration_number} - {self.title}"

    class Meta:
        ordering = ['-date_reported']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['case_type']),
            models.Index(fields=['is_archived']),
            models.Index(fields=['date_reported']),
            models.Index(fields=['date_of_incident']),
            models.Index(fields=['student', 'status']),
        ]


# =========================================
# 🔷 AUDIT LOG
# =========================================
class DisciplineAuditLog(models.Model):

    ACTION_CHOICES = (
        ('created', 'Created'),
        ('updated', 'Updated'),
        ('resolved', 'Resolved'),
        ('archived', 'Archived'),
    )

    case = models.ForeignKey(
        DisciplineCase,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        db_index=True
    )

    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)

    performed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        db_index=True
    )

    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    notes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.case} - {self.action} at {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['action']),
            models.Index(fields=['case']),
        ]


# =========================================
# 🔷 SIGNALS (AUDIT)
# =========================================
from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender=DisciplineCase)
def create_audit_log(sender, instance, created, **kwargs):
    if created:
        DisciplineAuditLog.objects.create(
            case=instance,
            action='created',
            performed_by=instance.reported_by
        )
    else:
        DisciplineAuditLog.objects.create(
            case=instance,
            action='updated',
            performed_by=instance.reported_by
        )


# =========================================
# 🔷 SUSPENSION MODEL
# =========================================
class SuspensionRecord(models.Model):

    STATUS_CHOICES = (
        ('active', 'Active'),
        ('completed', 'Completed'),
    )

    case = models.OneToOneField(
        DisciplineCase,
        on_delete=models.CASCADE,
        related_name='suspension'
    )

    start_date = models.DateField(db_index=True)
    end_date = models.DateField(db_index=True)

    actual_return_date = models.DateField(blank=True, null=True)

    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='active',
        db_index=True
    )

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    # 🔥 FIX: SAFE DURATION
    def duration(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return 0

    # 🔥 FIX: SAFE OVERDUE CHECK
    def is_overdue(self):
        if self.status != 'active':
            return False
        if not self.end_date:
            return False
        return self.end_date < now().date()

    # 🔥 FIX: SMART STATUS HANDLING
    def save(self, *args, **kwargs):

        today = now().date()

        if self.actual_return_date:
            self.status = 'completed'

        elif self.end_date and self.end_date < today:
            self.status = 'completed'

        else:
            self.status = 'active'

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.case} Suspension"

    class Meta:
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['start_date']),
            models.Index(fields=['end_date']),
        ]