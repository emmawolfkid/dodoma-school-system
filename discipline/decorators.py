from django.shortcuts import redirect
from django.contrib import messages
from .utils import has_discipline_permission


def discipline_permission_required(permission_type):
    def decorator(view_func):
        def wrapper(request, *args, **kwargs):

            if not request.user.is_authenticated:
                return redirect('login')

            if not has_discipline_permission(request.user, permission_type):
                messages.error(request, "You do not have permission to access Discipline Module")
                return redirect('dashboard')

            return view_func(request, *args, **kwargs)

        return wrapper
    return decorator