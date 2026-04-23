from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def dashboard_redirect(request):
    user = request.user

    if user.groups.filter(name='Admin').exists():
        return redirect('admin_dashboard')
    elif user.groups.filter(name='Doctor').exists():
        return redirect('doctor_dashboard')
    elif user.groups.filter(name='Receptionist').exists():
        return redirect('receptionist_dashboard')
    elif user.groups.filter(name='Patient').exists():
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