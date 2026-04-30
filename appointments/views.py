from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from accounts.models import DoctorProfile


@login_required
def appointment_list_view(request):
    return render(request, 'appointments/appointment_list.html')


@login_required
def doctor_list_view(request):
    doctors = DoctorProfile.objects.all()
    return render(request, 'appointments/doctor_list.html', {
        'doctors': doctors
    })


@login_required
def doctor_slots_view(request, doctor_id):
    doctor = DoctorProfile.objects.get(id=doctor_id)
    return render(request, 'appointments/doctor_slots.html', {
        'doctor': doctor
    })


@login_required
def book_appointment_view(request, doctor_id):
    doctor = DoctorProfile.objects.get(id=doctor_id)
    return render(request, 'appointments/book_appointment.html', {
        'doctor': doctor
    })