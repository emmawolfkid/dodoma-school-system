from .models import AuditLog

def log_action(user, action, description):
    AuditLog.objects.create(
        user=user,
        action=action,
        description=description
    )