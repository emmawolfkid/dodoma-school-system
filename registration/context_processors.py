from accounts.models import UserModule

def user_permissions(request):
    if request.user.is_authenticated:
        # Check if user has add permission for registration module
        has_add = UserModule.objects.filter(
            user=request.user,
            module__name='registration',
            is_approved=True,
            can_add=True
        ).exists()
        return {'user_can_add': has_add or request.user.is_superuser}
    return {'user_can_add': False}