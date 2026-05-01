from accounts.models import UserModule, Module

def has_discipline_permission(user, permission_type):

    # ✅ SUPERUSER BYPASS (VERY IMPORTANT)
    if user.is_superuser:
        return True

    try:
        module = Module.objects.get(name='discipline')
        user_module = UserModule.objects.get(
            user=user,
            module=module,
            is_approved=True
        )

        # ✅ MODULE ADMIN → FULL ACCESS
        if user_module.is_admin:
            return True

        if permission_type == 'view':
            return user_module.can_view

        if permission_type == 'add':
            return user_module.can_add

        if permission_type == 'edit':
            return user_module.can_edit

        if permission_type == 'delete':
            return user_module.can_delete

    except UserModule.DoesNotExist:
        return False

    return False