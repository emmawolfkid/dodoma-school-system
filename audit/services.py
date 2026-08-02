from .models import AuditLog


def log_action(user, action, instance, module, changes=None):
    AuditLog.objects.create(
        user=user,
        action=action,
        model_name=instance.__class__.__name__ if instance else None,
        object_id=str(instance.pk) if instance else None,
        module=module,
        changes=changes or {}
    )
