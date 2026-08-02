from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from registration.models import Student
from discipline.models import DisciplineCase
from academic.models import StudentMark
from .services import log_action
from .middleware import get_current_user


TRACKED_MODELS = [Student, DisciplineCase, StudentMark]

_old_data = {}


def to_dict(instance):
    data = {}
    for field in instance._meta.fields:
        try:
            data[field.name] = str(getattr(instance, field.name))
        except:
            data[field.name] = None
    return data


@receiver(pre_save)
def capture_old(sender, instance, **kwargs):
    if sender not in TRACKED_MODELS:
        return

    if not instance.pk:
        return

    try:
        old = sender.objects.get(pk=instance.pk)
        _old_data[id(instance)] = to_dict(old)
    except:
        pass


@receiver(post_save)
def log_changes(sender, instance, created, **kwargs):
    if sender not in TRACKED_MODELS:
        return

    new_data = to_dict(instance)

    if created:
        log_action(
            user=get_current_user(),
            action='create',
            instance=instance,
            module=sender._meta.app_label,
            changes={"new": new_data}
        )
    else:
        old_data = _old_data.pop(id(instance), {})

        changes = {}
        for key in old_data:
            if old_data.get(key) != new_data.get(key):
                changes[key] = {
                    "old": old_data.get(key),
                    "new": new_data.get(key)
                }

        if changes:
            log_action(
                user=get_current_user(),
                action='update',
                instance=instance,
                module=sender._meta.app_label,
                changes=changes
            )