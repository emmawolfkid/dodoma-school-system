from django.db.models.signals import post_migrate
from django.dispatch import receiver
from .models import Module


@receiver(post_migrate)
def create_default_modules(sender, **kwargs):
    modules = [
        "registration",
        "academic",
        "discipline",
        "certificate",
        "audit",
        "library",
        "health",
    ]

    for module_name in modules:
        Module.objects.get_or_create(name=module_name)