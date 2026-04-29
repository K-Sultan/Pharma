from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import DoctorProfile
from appointments.utils import get_available_slots

from .models import Appointment, AppointmentStatus
from .serializers import AppointmentSerializer, AppointmentSlotSerializer, DoctorProfileSerializer


def _get_patient_profile_or_none(user):
    return getattr(user, "patient_profile", None)


def _parse_time_value(value):
    if not value:
        return None

    for time_format in ("%H:%M:%S", "%H:%M", "%I:%M %p"):
        try:
            return datetime.strptime(value.strip(), time_format).time()
        except ValueError:
            continue

    return value


def _book_or_reschedule_appointment(*, doctor, patient, date, start_time, end_time, existing_appointment=None):
    if date <= timezone.localdate():
        return None, "future_only"

    conflicts = Appointment.objects.filter(date=date).exclude(status=AppointmentStatus.CANCELLED)
    if existing_appointment is not None:
        conflicts = conflicts.exclude(id=existing_appointment.id)

    conflicts = conflicts.filter(
        models.Q(doctor=doctor, start_time__lt=end_time, end_time__gt=start_time)
        | models.Q(patient=patient, start_time__lt=end_time, end_time__gt=start_time)
    )

    if conflicts.exists():
        return None, "conflict"

    if existing_appointment is None:
        appointment = Appointment.objects.create(
            doctor=doctor,
            patient=patient,
            date=date,
            start_time=start_time,
            end_time=end_time,
        )
        return appointment, None

    existing_appointment.date = date
    existing_appointment.start_time = start_time
    existing_appointment.end_time = end_time

    if existing_appointment.status == AppointmentStatus.CONFIRMED:
        existing_appointment.status = AppointmentStatus.PENDING

    existing_appointment.save(update_fields=["date", "start_time", "end_time", "status"])
    return existing_appointment, None


def _build_doctor_slots_context(request, doctor_id):
    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    patient = _get_patient_profile_or_none(request.user)
    appointment_to_reschedule_id = request.GET.get("appointment")
    appointment_to_reschedule = None
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)

    date_str = request.GET.get("date")
    if appointment_to_reschedule_id:
        if patient is None:
            return None, "Patient profile required."

        appointment_to_reschedule = get_object_or_404(
            Appointment,
            id=appointment_to_reschedule_id,
            patient=patient,
        )
        doctor = appointment_to_reschedule.doctor
        if not date_str:
            date_str = max(appointment_to_reschedule.date, tomorrow).strftime("%Y-%m-%d")

    slots = []
    selected_date = None
    if date_str:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return None, "Invalid date format. Use YYYY-MM-DD."

        slots = get_available_slots(
            doctor,
            selected_date,
            exclude_appointment_id=getattr(appointment_to_reschedule, "id", None),
        )

    return {
        "doctor": doctor,
        "slots": slots,
        "selected_date": date_str,
        "today": today,
        "tomorrow": tomorrow,
        "appointment_to_reschedule": appointment_to_reschedule,
        "slot_action_url": reverse("reschedule_appointment", args=[appointment_to_reschedule.id]) if appointment_to_reschedule else reverse("book_appointment", args=[doctor.id]),
    }, None


@login_required
def appointment_list_view(request):
    return render(request, "appointments/appointment_list.html")


@login_required
def doctor_list(request):
    doctors = DoctorProfile.objects.select_related("user")
    return render(request, "appointments/doctors_list.html", {"doctors": doctors})


@login_required
def doctor_slots(request, doctor_id):
    context, error_message = _build_doctor_slots_context(request, doctor_id)
    if context is None:
        messages.error(request, error_message)
        return redirect("doctor_list")

    return render(request, "appointments/doctor_slots.html", context)


@login_required
def book_appointment(request, doctor_id):
    if request.method != "POST":
        return redirect("doctor_slots", doctor_id=doctor_id)

    doctor = get_object_or_404(DoctorProfile, id=doctor_id)
    patient = _get_patient_profile_or_none(request.user)
    if patient is None:
        messages.error(request, "Patient profile required.")
        return redirect("doctor_slots", doctor_id=doctor.id)

    date = request.POST.get("date")
    start_time = _parse_time_value(request.POST.get("start_time"))
    end_time = _parse_time_value(request.POST.get("end_time"))

    if not date or not start_time or not end_time:
        messages.error(request, "Please choose a valid appointment slot.")
        return redirect("doctor_slots", doctor_id=doctor.id)

    parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    appointment, error_code = _book_or_reschedule_appointment(
        doctor=doctor,
        patient=patient,
        date=parsed_date,
        start_time=start_time,
        end_time=end_time,
    )

    if error_code == "future_only":
        messages.error(request, "You can only book appointments from tomorrow onward.")
        return redirect(f"{reverse('doctor_slots', args=[doctor.id])}?date={date}")

    if error_code == "conflict":
        messages.error(request, "That slot conflicts with an existing appointment.")
        return redirect(f"{reverse('doctor_slots', args=[doctor.id])}?date={date}")

    messages.success(request, "Appointment booked.")
    return redirect("patient_appointments")


@login_required
def reschedule_appointment(request, appointment_id):
    patient = _get_patient_profile_or_none(request.user)
    if patient is None:
        messages.error(request, "Patient profile required.")
        return redirect("patient_appointments")

    appointment = get_object_or_404(Appointment, id=appointment_id, patient=patient)
    appointment_start = timezone.make_aware(datetime.combine(appointment.date, appointment.start_time))

    if timezone.now() >= appointment_start:
        messages.error(request, "This appointment can only be rescheduled before its start time.")
        return redirect("patient_appointments")

    if request.method != "POST":
        return redirect(f"{reverse('doctor_slots', args=[appointment.doctor.id])}?appointment={appointment.id}")

    date = request.POST.get("date")
    start_time = _parse_time_value(request.POST.get("start_time"))
    end_time = _parse_time_value(request.POST.get("end_time"))

    if not date or not start_time or not end_time:
        messages.error(request, "Please choose a valid appointment slot.")
        return redirect(f"{reverse('doctor_slots', args=[appointment.doctor.id])}?appointment={appointment.id}")

    parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    _, error_code = _book_or_reschedule_appointment(
        doctor=appointment.doctor,
        patient=appointment.patient,
        date=parsed_date,
        start_time=start_time,
        end_time=end_time,
        existing_appointment=appointment,
    )

    if error_code == "future_only":
        messages.error(request, "You can only reschedule appointments to tomorrow or later.")
        return redirect(f"{reverse('doctor_slots', args=[appointment.doctor.id])}?appointment={appointment.id}&date={date}")

    if error_code == "conflict":
        messages.error(request, "That slot conflicts with an existing appointment.")
        return redirect(f"{reverse('doctor_slots', args=[appointment.doctor.id])}?appointment={appointment.id}&date={date}")

    messages.success(request, "Appointment rescheduled.")
    return redirect("patient_appointments")


@login_required
def cancel_appointment(request, appointment_id):
    if request.method != "POST":
        return redirect("patient_appointments")

    patient = _get_patient_profile_or_none(request.user)
    if patient is None:
        messages.error(request, "Patient profile required.")
        return redirect("patient_appointments")

    appointment = get_object_or_404(Appointment, id=appointment_id, patient=patient)

    if appointment.status == AppointmentStatus.CANCELLED:
        messages.info(request, "That appointment is already cancelled.")
        return redirect("patient_appointments")

    if appointment.date < timezone.localdate():
        messages.error(request, "Past appointments cannot be cancelled.")
        return redirect("patient_appointments")

    appointment.status = AppointmentStatus.CANCELLED
    appointment.save(update_fields=["status"])
    messages.success(request, "Appointment cancelled.")
    return redirect("patient_appointments")


@login_required
def patient_appointments(request):
    patient = _get_patient_profile_or_none(request.user)
    if patient is None:
        messages.error(request, "Patient profile required.")
        return redirect("appointment_list")

    today = timezone.localdate()
    current_time = timezone.localtime().time()

    upcoming = patient.appointments.filter(date__gte=today).exclude(status=AppointmentStatus.CANCELLED).order_by("date", "start_time")
    past = patient.appointments.filter(date__lt=today).exclude(status=AppointmentStatus.CANCELLED)
    cancelled = patient.appointments.filter(status=AppointmentStatus.CANCELLED)

    upcoming_items = []
    for appointment in upcoming:
        appointment.can_reschedule = appointment.date > today or (
            appointment.date == today and appointment.start_time > current_time
        )
        upcoming_items.append(appointment)

    return render(request, "appointments/patient_appointments.html", {
        "upcoming": upcoming_items,
        "past": past,
        "cancelled": cancelled,
    })


class AppointmentApiRootView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "doctors_url": "/appointments/api/doctors/",
                "patient_appointments_url": "/appointments/api/appointments/",
                "note": "Use the API endpoints for doctors, slots, booking, rescheduling, and cancellation.",
            }
        )


class DoctorListAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        doctors = DoctorProfile.objects.select_related("user")
        serializer = DoctorProfileSerializer(doctors, many=True)
        return Response({"doctors": serializer.data})


class DoctorSlotsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, doctor_id):
        context, error_message = _build_doctor_slots_context(request, doctor_id)
        if context is None:
            return Response({"detail": error_message}, status=status.HTTP_403_FORBIDDEN if error_message == "Patient profile required." else status.HTTP_400_BAD_REQUEST)

        appointment_to_reschedule = context["appointment_to_reschedule"]
        return Response(
            {
                "doctor": DoctorProfileSerializer(context["doctor"]).data,
                "selected_date": context["selected_date"],
                "earliest_bookable_date": context["tomorrow"],
                "appointment_to_reschedule": AppointmentSerializer(appointment_to_reschedule).data if appointment_to_reschedule else None,
                "slots": [
                    {"start_time": slot_start, "end_time": slot_end}
                    for slot_start, slot_end in context["slots"]
                ],
            }
        )


class BookAppointmentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, doctor_id):
        doctor = get_object_or_404(DoctorProfile, id=doctor_id)
        patient = _get_patient_profile_or_none(request.user)
        if patient is None:
            return Response({"detail": "Patient profile required."}, status=status.HTTP_403_FORBIDDEN)

        serializer = AppointmentSlotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appointment, error_code = _book_or_reschedule_appointment(
            doctor=doctor,
            patient=patient,
            date=serializer.validated_data["date"],
            start_time=serializer.validated_data["start_time"],
            end_time=serializer.validated_data["end_time"],
        )

        if error_code == "future_only":
            return Response(
                {"detail": "You can only book appointments from tomorrow onward."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if error_code == "conflict":
            return Response(
                {"detail": "That slot conflicts with an existing appointment."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({"appointment": AppointmentSerializer(appointment).data}, status=status.HTTP_201_CREATED)


class RescheduleAppointmentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, appointment_id):
        patient = _get_patient_profile_or_none(request.user)
        if patient is None:
            return Response({"detail": "Patient profile required."}, status=status.HTTP_403_FORBIDDEN)

        appointment = get_object_or_404(Appointment, id=appointment_id, patient=patient)
        appointment_start = timezone.make_aware(datetime.combine(appointment.date, appointment.start_time))

        if timezone.now() >= appointment_start:
            return Response(
                {"detail": "This appointment can only be rescheduled before its start time."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = AppointmentSlotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appointment, error_code = _book_or_reschedule_appointment(
            doctor=appointment.doctor,
            patient=appointment.patient,
            date=serializer.validated_data["date"],
            start_time=serializer.validated_data["start_time"],
            end_time=serializer.validated_data["end_time"],
            existing_appointment=appointment,
        )

        if error_code == "future_only":
            return Response(
                {"detail": "You can only reschedule appointments to tomorrow or later."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if error_code == "conflict":
            return Response(
                {"detail": "That slot conflicts with an existing appointment."},
                status=status.HTTP_409_CONFLICT,
            )

        return Response({"appointment": AppointmentSerializer(appointment).data})


class CancelAppointmentAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, appointment_id):
        patient = _get_patient_profile_or_none(request.user)
        if patient is None:
            return Response({"detail": "Patient profile required."}, status=status.HTTP_403_FORBIDDEN)

        appointment = get_object_or_404(Appointment, id=appointment_id, patient=patient)

        if appointment.status == AppointmentStatus.CANCELLED:
            return Response({"detail": "That appointment is already cancelled."})

        if appointment.date < timezone.localdate():
            return Response(
                {"detail": "Past appointments cannot be cancelled."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        appointment.status = AppointmentStatus.CANCELLED
        appointment.save(update_fields=["status"])
        return Response({"appointment": AppointmentSerializer(appointment).data})


class PatientAppointmentsAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        patient = _get_patient_profile_or_none(request.user)
        if patient is None:
            return Response({"detail": "Patient profile required."}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        current_time = timezone.localtime().time()

        upcoming = patient.appointments.filter(date__gte=today).exclude(status=AppointmentStatus.CANCELLED).order_by("date", "start_time")
        past = patient.appointments.filter(date__lt=today).exclude(status=AppointmentStatus.CANCELLED)
        cancelled = patient.appointments.filter(status=AppointmentStatus.CANCELLED)

        upcoming_data = []
        for appointment in upcoming:
            item = AppointmentSerializer(appointment).data
            item["can_reschedule"] = appointment.date > today or (
                appointment.date == today and appointment.start_time > current_time
            )
            upcoming_data.append(item)

        return Response(
            {
                "upcoming": upcoming_data,
                "past": AppointmentSerializer(past, many=True).data,
                "cancelled": AppointmentSerializer(cancelled, many=True).data,
            }
        )