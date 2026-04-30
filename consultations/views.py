from rest_framework import generics, permissions
from .models import ConsultationRecord
from .serializers import ConsultationRecordSerializer

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from accounts.decorators import role_required
from accounts.models import UserRole
from appointments.models import Appointment, AppointmentStatus
from .models import ConsultationRecord, PrescriptionItem


class ConsultationRecordListCreateView(generics.ListCreateAPIView):
    queryset = ConsultationRecord.objects.select_related("appointment").prefetch_related("prescriptions")
    serializer_class = ConsultationRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

class ConsultationRecordDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ConsultationRecord.objects.select_related("appointment").prefetch_related("prescriptions")
    serializer_class = ConsultationRecordSerializer
    permission_classes = [permissions.IsAuthenticated]



@login_required
@role_required(UserRole.DOCTOR)
def fill_consultation_view(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related('doctor__user', 'patient__user'),
        id=appointment_id,
        doctor__user=request.user
    )

    if appointment.status != AppointmentStatus.CHECKED_IN:
        messages.error(request, 'Only checked-in appointments can be completed.')
        return redirect('doctor_queue')

    consultation, created = ConsultationRecord.objects.get_or_create(
        appointment=appointment
    )

    if request.method == 'POST':
        notes = request.POST.get('notes')
        diagnosis = request.POST.get('diagnosis')
        requested_tests = request.POST.get('requested_tests')

        drug = request.POST.get('drug')
        dose = request.POST.get('dose')
        duration = request.POST.get('duration')

        consultation.notes = notes
        consultation.diagnosis = diagnosis
        consultation.requested_tests = requested_tests
        consultation.save()

        if drug and dose and duration:
            PrescriptionItem.objects.create(
                consultation=consultation,
                drug=drug,
                dose=dose,
                duration=duration
            )

        appointment.status = AppointmentStatus.COMPLETED
        appointment.save(update_fields=['status'])

        messages.success(request, 'Consultation saved and appointment completed.')
        return redirect('doctor_queue')

    return render(request, 'consultations/fill_consultation.html', {
        'appointment': appointment,
        'consultation': consultation
    })
