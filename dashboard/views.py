from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

from accounts.models import UserRole

@login_required
def dashboard_redirect(request):
    user = request.user

    if user.role == UserRole.ADMIN or user.is_superuser:
        return redirect('admin_dashboard')
    elif user.role == UserRole.DOCTOR:
        return redirect('doctor_dashboard')
    elif user.role == UserRole.RECEPTIONIST:
        return redirect('receptionist_dashboard')
    elif user.role == UserRole.PATIENT:
        return redirect('patient_dashboard')

    return redirect('home')


@login_required
def patient_dashboard(request):
    return render(request, 'dashboard/patient_dashboard.html')


@login_required
def doctor_dashboard(request):
    return render(request, 'dashboard/doctor_dashboard.html')


@login_required
def receptionist_dashboard(request):
    return render(request, 'dashboard/receptionist_dashboard.html')


@login_required
def admin_dashboard(request):
    return render(request, 'dashboard/admin_dashboard.html')