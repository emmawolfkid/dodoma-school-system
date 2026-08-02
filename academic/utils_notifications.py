import logging

from django.conf import settings
from django.core.mail import send_mail

from .models import Notification

logger = logging.getLogger(__name__)


def create_notification(user, message, email=False, email_subject=None):
    """
    Always creates the in-app Notification (shown in the bell on every
    page). Pass email=True only for events worth a real email — keeps
    outbound mail volume (and mailbox storage) down to what matters:
    results published, discipline/suspension actions, account/password
    changes — not routine assignment housekeeping.
    """
    if user is None:
        return

    Notification.objects.create(user=user, message=message)

    if not email or not getattr(user, 'email', None):
        return

    try:
        send_mail(
            subject=email_subject or f"{settings.ADMIN_SITE_TITLE} notification",
            message=message,
            from_email=None,  # uses DEFAULT_FROM_EMAIL
            recipient_list=[user.email],
            fail_silently=False,
        )
    except Exception:
        # Email delivery must never break the request that triggered it —
        # the in-app notification above already landed regardless.
        logger.exception("Failed to send notification email to %s", user.email)


def notify_many(users, message, email=False, email_subject=None):
    """Notify a group of users (e.g. all admins for a module) at once."""
    for user in users:
        create_notification(user, message, email=email, email_subject=email_subject)


def notify_module_admins(module_name, message, email=False, email_subject=None, include_superusers=True):
    """Notify everyone approved as an admin for a given module (e.g. 'discipline', 'registration')."""
    from django.db.models import Q
    from accounts.models import User

    admins = User.objects.filter(
        usermodule__module__name=module_name,
        usermodule__is_admin=True,
        usermodule__is_approved=True,
    )
    if include_superusers:
        admins = User.objects.filter(Q(pk__in=admins.values('pk')) | Q(is_superuser=True))

    notify_many(admins.distinct(), message, email=email, email_subject=email_subject)
