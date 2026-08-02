from django.contrib import admin
from .models import AuditLog
from accounts.models import UserModule


def has_audit_access(user):
    # AnonymousUser has no row in the DB — filtering UserModule by it
    # raises a TypeError, and this runs even on the admin login page.
    if not user.is_authenticated:
        return False

    return UserModule.objects.filter(
        user=user,
        module__name='audit',
        is_approved=True
    ).exists()


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'module', 'timestamp')

    def has_view_permission(self, request, obj=None):
        return has_audit_access(request.user)

    def has_module_permission(self, request):
        return has_audit_access(request.user)

    # Audit logs must be immutable: no one, including superusers, can
    # create/edit/delete an entry through the admin — only view it.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False