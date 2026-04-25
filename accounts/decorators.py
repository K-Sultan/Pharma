from django.shortcuts import redirect

from .models import UserRole


def role_required(*allowed_roles):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            if request.user.role not in allowed_roles:
                return redirect('dashboard_redirect')
            return view_func(request, *args, **kwargs)

        return _wrapped_view

    return decorator


def admin_staff_required(view_func):
    return role_required(UserRole.ADMIN)(view_func)