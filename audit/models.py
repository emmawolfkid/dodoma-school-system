from django.db import models
from django.conf import settings

User = settings.AUTH_USER_MODEL


class AuditLog(models.Model):

    ACTION_CHOICES = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
    )

    # WHO
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    # WHAT
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)

    # WHICH MODEL
    model_name = models.CharField(max_length=100, null=True, blank=True)
    object_id = models.CharField(max_length=255, null=True, blank=True)

    # CHANGES
    changes = models.JSONField(null=True, blank=True)

    # MODULE (academic, discipline...)
    module = models.CharField(max_length=100)

    # TIME
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} - {self.model_name} - {self.timestamp}"

    class Meta:
        ordering = ['-timestamp']