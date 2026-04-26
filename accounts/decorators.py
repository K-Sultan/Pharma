from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from .models import UserRole


def role_required(required_role):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            if request.user.role != required_role:
                messages.error(request, "You do not have permission to access this page.")
                return redirect('dashboard_redirect')

            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


def admin_staff_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if request.user.is_superuser or request.user.role == UserRole.ADMIN:
            return view_func(request, *args, **kwargs)

        messages.error(request, "Only admins can access this page.")
        return redirect('dashboard_redirect')

    return wrapper