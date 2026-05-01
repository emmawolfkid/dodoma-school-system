from accounts.models import UserModule

def has_permission(user, perm):
    # 🔥 SUPERUSER
    if user.is_superuser:
        return True

    # 🔥 MODULE ADMIN
    if UserModule.objects.filter(
        user=user,
        module__name='registration',
        is_admin=True,
        is_approved=True
    ).exists():
        return True

    # 🔥 NORMAL USER
    return UserModule.objects.filter(
        user=user,
        module__name='registration',
        is_approved=True,
        **{f'can_{perm}': True}
    ).exists()