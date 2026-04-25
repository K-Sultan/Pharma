from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction

from .decorators import admin_staff_required
from .forms import DoctorCreateForm, PatientRegistrationForm, ReceptionistCreateForm
from .models import DoctorProfile, PatientProfile, ReceptionistProfile, UserRole

def register_view(request):
    if request.method == 'POST':
        form = PatientRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            password = form.cleaned_data['password']

            user.role = UserRole.PATIENT
            user.set_password(password)
            user.save()
            PatientProfile.objects.create(user=user)

            messages.success(request, 'Account created successfully.')
            return redirect('login')
    else:
        form = PatientRegistrationForm()

    return render(request, 'accounts/register.html', {'form': form})


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        user = authenticate(request, username=username, password=password)

        if user is not None:
            login(request, user)
            return redirect('dashboard_redirect')
        else:
            messages.error(request, 'Invalid username or password.')

    return render(request, 'accounts/login.html')


def logout_view(request):
    logout(request)
    return redirect('home')


@login_required
@admin_staff_required
def create_doctor_view(request):
    if request.method == 'POST':
        form = DoctorCreateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                DoctorProfile.objects.create(
                    user=user,
                    license_number=form.cleaned_data['license_number'],
                    specialization=form.cleaned_data['specialization'],
                    department=form.cleaned_data['department'],
                    bio=form.cleaned_data['bio'],
                )
            messages.success(request, 'Doctor account created successfully.')
            return redirect('admin_dashboard')
    else:
        form = DoctorCreateForm()

    return render(request, 'accounts/create_doctor.html', {'form': form})


@login_required
@admin_staff_required
def create_receptionist_view(request):
    if request.method == 'POST':
        form = ReceptionistCreateForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = form.save()
                ReceptionistProfile.objects.create(
                    user=user,
                    department=form.cleaned_data['department'],
                    phone_extension=form.cleaned_data['phone_extension'],
                )
            messages.success(request, 'Receptionist account created successfully.')
            return redirect('admin_dashboard')
    else:
        form = ReceptionistCreateForm()

    return render(request, 'accounts/create_receptionist.html', {'form': form})