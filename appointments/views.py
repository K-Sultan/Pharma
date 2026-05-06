import csv
from datetime import datetime, timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import models
from django.db.models import Count, Q
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.dateparse import parse_date
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import DoctorProfile, PatientProfile, UserRole
from appointments.utils import get_available_slots
from consultations.models import ConsultationRecord
from consultations.serializers import ConsultationRecordSerializer

from .models import Appointment, AppointmentReschedule, AppointmentStatus
from .serializers import (
    AppointmentQueueSerializer,
    AppointmentSerializer,
    AppointmentSlotSerializer,
    AppointmentStatusUpdateSerializer,
    DoctorProfileSerializer,
)
from accounts.permissions import IsDoctor, IsPatient, IsReceptionist, IsAdmin
from accounts.decorators import role_required
from accounts.models import UserRole

def _get_patient_profile_or_none(user):
    return getattr(user, "patient_profile", None)


def _get_appointment_queryset():
    return Appointment.objects.select_related(
        "doctor__user",
        "patient__user",
        "consultation_record",
    )


def _parse_filter_date(value, field_name):
    if not value:
        return None

    parsed_value = parse_date(value)
    if parsed_value is None:
        raise ValidationError({field_name: "Use YYYY-MM-DD format."})

    return parsed_value


def _apply_appointment_filters(queryset, params):
    appointment_id = params.get("appointment_id") or params.get("id")
    if appointment_id:
        try:
            queryset = queryset.filter(id=int(appointment_id))
        except (TypeError, ValueError):
            raise ValidationError({"id": "Appointment id must be an integer."})

    doctor_id = params.get("doctor_id")
    if doctor_id:
        try:
            queryset = queryset.filter(doctor_id=int(doctor_id))
        except (TypeError, ValueError):
            raise ValidationError({"doctor_id": "Doctor id must be an integer."})

    patient_id = params.get("patient_id")
    if patient_id:
        try:
            queryset = queryset.filter(patient_id=int(patient_id))
        except (TypeError, ValueError):
            raise ValidationError({"patient_id": "Patient id must be an integer."})

    patient_name = params.get("patient_name")
    if patient_name:
        queryset = queryset.filter(
            Q(patient__user__username__icontains=patient_name)
            | Q(patient__user__first_name__icontains=patient_name)
            | Q(patient__user__last_name__icontains=patient_name)
        )

    search_value = params.get("search")
    if search_value:
        search_value = search_value.strip()
        if search_value.isdigit():
            queryset = queryset.filter(id=int(search_value))
        else:
            queryset = queryset.filter(
                Q(patient__user__username__icontains=search_value)
                | Q(patient__user__first_name__icontains=search_value)
                | Q(patient__user__last_name__icontains=search_value)
            )

    status_value = params.get("status")
    if status_value:
        valid_statuses = {choice for choice, _ in AppointmentStatus.choices}
        if status_value not in valid_statuses:
            raise ValidationError({"status": "Invalid appointment status."})
        queryset = queryset.filter(status=status_value)

    start_date = _parse_filter_date(params.get("start_date"), "start_date")
    end_date = _parse_filter_date(params.get("end_date"), "end_date")

    if start_date and end_date and start_date > end_date:
        raise ValidationError({"date_range": "start_date cannot be after end_date."})

    if start_date:
        queryset = queryset.filter(date__gte=start_date)
    if end_date:
        queryset = queryset.filter(date__lte=end_date)

    return queryset


def _upsert_consultation_record(appointment, check_in_time):
    return ConsultationRecord.objects.update_or_create(
        appointment=appointment,
        defaults={"check_in_time": check_in_time},
    )


def _parse_time_value(value):
    if not value:
        return None

    for time_format in ("%H:%M:%S", "%H:%M", "%I:%M %p"):
        try:
            return datetime.strptime(value.strip(), time_format).time()
        except ValueError:
            continue

    return value


def _user_can_manage_appointments(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.role in {UserRole.DOCTOR, UserRole.RECEPTIONIST, UserRole.ADMIN})
    )


def _appointment_management_queryset():
    return _get_appointment_queryset()


def _staff_appointment_filter_counts(queryset):
    return {
        "all": queryset.count(),
        "pending": queryset.filter(status=AppointmentStatus.PENDING).count(),
        "confirmed": queryset.filter(status=AppointmentStatus.CONFIRMED).count(),
        "checked_in": queryset.filter(status=AppointmentStatus.CHECKED_IN).count(),
        "declined": queryset.filter(status=AppointmentStatus.DECLINED).count(),
        "no_show": queryset.filter(status=AppointmentStatus.NO_SHOW).count(),
    }


def _apply_staff_appointment_tab(queryset, tab):
    if tab == "pending":
        return queryset.filter(status=AppointmentStatus.PENDING)
    if tab == "confirmed":
        return queryset.filter(status=AppointmentStatus.CONFIRMED)
    if tab == "checked_in":
        return queryset.filter(status=AppointmentStatus.CHECKED_IN)
    if tab == "declined":
        return queryset.filter(status=AppointmentStatus.DECLINED)
    if tab == "no_show":
        return queryset.filter(status=AppointmentStatus.NO_SHOW)
    return queryset


def _mark_overdue_appointments_as_no_show(queryset):
    today = timezone.localdate()

    overdue_appointments = queryset.filter(date__lt=today).exclude(
        status__in=[
            AppointmentStatus.CHECKED_IN,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.CANCELLED,
            AppointmentStatus.NO_SHOW,
        ]
    )

    return overdue_appointments.update(status=AppointmentStatus.NO_SHOW)


def _update_staff_appointment_status(*, appointment, new_status):
    if appointment.status == AppointmentStatus.CANCELLED:
        return None, "cancelled"

    if new_status not in {AppointmentStatus.CONFIRMED, AppointmentStatus.DECLINED}:
        return None, "invalid"

    if appointment.status == new_status:
        return appointment, "unchanged"

    appointment.status = new_status
    appointment.save(update_fields=["status"])
    return appointment, None


def _set_appointment_no_show(*, appointment):
    if appointment.status == AppointmentStatus.CANCELLED:
        return None, "cancelled"
    if appointment.date > timezone.localdate():
        return None, "future_only"
    if appointment.status == AppointmentStatus.CHECKED_IN or getattr(appointment, "consultation_record", None) is not None:
        return None, "checked_in"
    if appointment.status == AppointmentStatus.COMPLETED:
        return None, "completed"
    if appointment.status == AppointmentStatus.NO_SHOW:
        return appointment, "unchanged"

    appointment.status = AppointmentStatus.NO_SHOW
    appointment.save(update_fields=["status"])
    return appointment, None


def _parse_slot_value(value):
    if not value:
        return None, None

    try:
        start_time_value, end_time_value = value.split("|", 1)
    except ValueError:
        return None, None

    return _parse_time_value(start_time_value), _parse_time_value(end_time_value)


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


def _create_reschedule_record(
    *,
    appointment,
    changed_by,
    old_date,
    old_start_time,
    old_end_time,
    new_date,
    new_start_time,
    new_end_time,
    reason="",
):
    if (
        old_date == new_date
        and old_start_time == new_start_time
        and old_end_time == new_end_time
    ):
        return None

    return AppointmentReschedule.objects.create(
        appointment=appointment,
        changed_by=changed_by,
        old_date=old_date,
        old_start_time=old_start_time,
        old_end_time=old_end_time,
        new_date=new_date,
        new_start_time=new_start_time,
        new_end_time=new_end_time,
        reason=reason,
    )


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


def _build_receptionist_reschedule_context(appointment, date_str=None):
    today = timezone.localdate()
    tomorrow = today + timedelta(days=1)

    if not date_str:
        date_str = max(appointment.date, tomorrow).strftime("%Y-%m-%d")

    try:
        selected_date = datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None, "Invalid date format. Use YYYY-MM-DD."

    slots = get_available_slots(
        appointment.doctor,
        selected_date,
        exclude_appointment_id=appointment.id,
    )

    return {
        "doctor": appointment.doctor,
        "slots": slots,
        "selected_date": date_str,
        "today": today,
        "tomorrow": tomorrow,
        "appointment_to_reschedule": appointment,
        "slot_action_url": reverse("receptionist_reschedule_appointment", args=[appointment.id]),
    }, None



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
    if start_time is None or end_time is None:
        start_time, end_time = _parse_slot_value(request.POST.get("slot"))

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
    if start_time is None or end_time is None:
        start_time, end_time = _parse_slot_value(request.POST.get("slot"))
    reason = (request.POST.get("reason") or "").strip()

    if not date or not start_time or not end_time:
        messages.error(request, "Please choose a valid appointment slot.")
        return redirect(f"{reverse('doctor_slots', args=[appointment.doctor.id])}?appointment={appointment.id}")

    parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
    old_date = appointment.date
    old_start_time = appointment.start_time
    old_end_time = appointment.end_time

    with transaction.atomic():
        _, error_code = _book_or_reschedule_appointment(
            doctor=appointment.doctor,
            patient=appointment.patient,
            date=parsed_date,
            start_time=start_time,
            end_time=end_time,
            existing_appointment=appointment,
        )

        if error_code is None:
            _create_reschedule_record(
                appointment=appointment,
                changed_by=request.user,
                old_date=old_date,
                old_start_time=old_start_time,
                old_end_time=old_end_time,
                new_date=parsed_date,
                new_start_time=start_time,
                new_end_time=end_time,
                reason=reason,
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
        return redirect("appointments_hub")

    today = timezone.localdate()
    current_time = timezone.localtime().time()

    upcoming = (
        patient.appointments.filter(date__gte=today)
        .exclude(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW])
        .order_by("date", "start_time")
    )
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


@login_required
def appointments_hub(request):
    if not _user_can_manage_appointments(request.user):
        messages.error(request, "You do not have permission to access this page.")
        return redirect("dashboard_redirect")

    tab = request.GET.get("tab") or "pending"
    queryset = _appointment_management_queryset()

    _mark_overdue_appointments_as_no_show(queryset)

    if request.user.role == UserRole.DOCTOR and not request.user.is_superuser:
        doctor_profile = get_object_or_404(DoctorProfile, user=request.user)
        queryset = queryset.filter(doctor=doctor_profile)

    try:
        filtered_queryset = _apply_appointment_filters(queryset, request.GET)
    except ValidationError:
        messages.error(request, "Please enter valid appointment filters.")
        filtered_queryset = queryset

    appointments = _apply_staff_appointment_tab(filtered_queryset, tab).order_by("date", "start_time")

    tab_querystrings = {}
    for tab_name in ["pending", "confirmed","checked_in", "declined", "no_show", "all"]:
        query_params = request.GET.copy()
        query_params["tab"] = tab_name
        tab_querystrings[tab_name] = query_params.urlencode()

    doctor_options = DoctorProfile.objects.select_related("user").order_by(
        "user__first_name",
        "user__last_name",
        "user__username",
    )
    patient_options = PatientProfile.objects.select_related("user").order_by(
        "user__first_name",
        "user__last_name",
        "user__username",
    )

    return render(request, "appointments/manage_appointments.html", {
        "appointments": appointments,
        "tab": tab,
        "counts": _staff_appointment_filter_counts(filtered_queryset),
        "filters": {
            "search": request.GET.get("search", ""),
            "doctor_id": request.GET.get("doctor_id", ""),
            "patient_id": request.GET.get("patient_id", ""),
            "start_date": request.GET.get("start_date", ""),
            "end_date": request.GET.get("end_date", ""),
        },
        "doctor_options": doctor_options,
        "patient_options": patient_options,
        "tab_querystrings": tab_querystrings,
        "clear_filters_url": f"{reverse('appointments_hub')}?tab={tab}",
    })


@login_required
def staff_appointment_status_update(request, appointment_id):
    if not _user_can_manage_appointments(request.user):
        messages.error(request, "You do not have permission to update appointments.")
        return redirect("dashboard_redirect")

    if request.method != "POST":
        return redirect("appointments_hub")

    appointment = get_object_or_404(_get_appointment_queryset(), id=appointment_id)
    action = request.POST.get("action")
    tab = request.POST.get("tab") or "pending"

    if action == "confirm":
        new_status = AppointmentStatus.CONFIRMED
        success_message = "Appointment confirmed."
    elif action == "decline":
        new_status = AppointmentStatus.DECLINED
        success_message = "Appointment declined."
    elif action == "no_show":
        new_status = AppointmentStatus.NO_SHOW
        success_message = "Appointment marked as no-show."
    else:
        messages.error(request, "Invalid appointment action.")
        return redirect(f"{reverse('appointments_hub')}?tab={tab}")

    if new_status == AppointmentStatus.NO_SHOW:
        _, error_code = _set_appointment_no_show(appointment=appointment)
    else:
        _, error_code = _update_staff_appointment_status(appointment=appointment, new_status=new_status)

    if error_code == "cancelled":
        messages.error(request, "Cancelled appointments cannot be updated.")
    elif error_code == "future_only":
        messages.error(request, "Future appointments cannot be marked as no-show.")
    elif error_code == "checked_in":
        messages.error(request, "Checked-in appointments cannot be marked as no-show.")
    elif error_code == "completed":
        messages.error(request, "Completed appointments cannot be marked as no-show.")
    elif error_code == "unchanged":
        messages.info(request, "That appointment is already in the requested status.")
    elif error_code == "invalid":
        messages.error(request, "Unsupported status transition.")
    else:
        messages.success(request, success_message)

    return redirect(f"{reverse('appointments_hub')}?tab={tab}")


class AppointmentApiRootView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(
            {
                "doctors_url": "/appointments/api/doctors/",
                "doctor_daily_queue_url": "/appointments/api/doctors/<doctor_id>/queue/",
                "patient_appointments_url": "/appointments/api/appointments/",
                "appointment_check_in_url": "/appointments/api/appointments/<appointment_id>/check-in/",
                "appointment_status_url": "/appointments/api/appointments/<appointment_id>/status/",
                "appointment_search_url": "/appointments/api/appointments/search/",
                "appointment_csv_export_url": "/appointments/api/appointments/export/csv/",
                "admin_analytics_url": "/appointments/api/admin/analytics/",
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


class AppointmentCheckInAPIView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, appointment_id):
        appointment = get_object_or_404(_get_appointment_queryset(), id=appointment_id)

        if appointment.date != timezone.localdate():
            return Response(
                {"detail": "Only today's appointments can be checked in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if appointment.status in {
            AppointmentStatus.CANCELLED,
            AppointmentStatus.DECLINED,
            AppointmentStatus.COMPLETED,
            AppointmentStatus.NO_SHOW,
        }:
            return Response(
                {"detail": f"Appointments with status '{appointment.status}' cannot be checked in."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        checked_in_at = timezone.now()
        appointment.status = AppointmentStatus.CHECKED_IN
        appointment.save(update_fields=["status"])

        consultation_record, created = _upsert_consultation_record(
            appointment,
            checked_in_at,
        )

        return Response(
            {
                "appointment": AppointmentSerializer(appointment).data,
                "consultation_record": ConsultationRecordSerializer(consultation_record).data,
                "consultation_record_created": created,
            }
        )


class DoctorDailyQueueAPIView(APIView):
    permission_classes = [IsReceptionist | IsAdmin | IsDoctor]

    def get(self, request, doctor_id):
        queryset = (
            _get_appointment_queryset()
            .filter(
                doctor_id=doctor_id,
                date=timezone.localdate(),
                status=AppointmentStatus.CHECKED_IN,
            )
            .order_by("consultation_record__check_in_time", "start_time")
        )

        return Response(
            {
                "doctor_id": doctor_id,
                "date": timezone.localdate(),
                "appointments": AppointmentQueueSerializer(queryset, many=True).data,
            }
        )


class BookAppointmentAPIView(APIView):
    permission_classes = [IsPatient]

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
    permission_classes = [IsPatient | IsReceptionist]

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
        reason = (serializer.validated_data.get("reason") or "").strip()

        old_date = appointment.date
        old_start_time = appointment.start_time
        old_end_time = appointment.end_time

        with transaction.atomic():
            appointment, error_code = _book_or_reschedule_appointment(
                doctor=appointment.doctor,
                patient=appointment.patient,
                date=serializer.validated_data["date"],
                start_time=serializer.validated_data["start_time"],
                end_time=serializer.validated_data["end_time"],
                existing_appointment=appointment,
            )

            if error_code is None:
                _create_reschedule_record(
                    appointment=appointment,
                    old_date=old_date,
                    old_start_time=old_start_time,
                    old_end_time=old_end_time,
                    new_date=serializer.validated_data["date"],
                    new_start_time=serializer.validated_data["start_time"],
                    new_end_time=serializer.validated_data["end_time"],
                    reason=reason,
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
    permission_classes = [IsPatient]

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


class AppointmentStatusUpdateAPIView(APIView):
    permission_classes = [IsDoctor | IsReceptionist | IsAdmin]

    def post(self, request, appointment_id):
        appointment = get_object_or_404(_get_appointment_queryset(), id=appointment_id)
        serializer = AppointmentStatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        new_status = serializer.validated_data["status"]

        if new_status in {AppointmentStatus.CONFIRMED, AppointmentStatus.DECLINED}:
            appointment, error_code = _update_staff_appointment_status(appointment=appointment, new_status=new_status)

            if error_code == "cancelled":
                return Response(
                    {"detail": "Cancelled appointments cannot be updated."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response({"appointment": AppointmentSerializer(appointment).data})

        if new_status == AppointmentStatus.NO_SHOW:
            appointment, error_code = _set_appointment_no_show(appointment=appointment)

            if error_code == "cancelled":
                return Response(
                    {"detail": "Cancelled appointments cannot be updated."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if error_code == "future_only":
                return Response(
                    {"detail": "Future appointments cannot be marked as no-show."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if error_code == "checked_in":
                return Response(
                    {"detail": "Checked-in appointments cannot be marked as no-show."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if error_code == "completed":
                return Response(
                    {"detail": "Completed appointments cannot be marked as no-show."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            return Response({"appointment": AppointmentSerializer(appointment).data})

        if appointment.status == AppointmentStatus.CANCELLED:
            return Response(
                {"detail": "Cancelled appointments cannot be updated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if new_status == AppointmentStatus.COMPLETED:
            consultation_record = getattr(appointment, "consultation_record", None)
            if consultation_record is None:
                return Response(
                    {"detail": "A consultation record is required before marking an appointment as completed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if appointment.status == AppointmentStatus.NO_SHOW:
                return Response(
                    {"detail": "A no-show appointment cannot be marked as completed."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        appointment.status = new_status
        appointment.save(update_fields=["status"])
        return Response({"appointment": AppointmentSerializer(appointment).data})


class AppointmentSearchAPIView(APIView):
    permission_classes = [IsReceptionist | IsAdmin]

    def get(self, request):
        queryset = _apply_appointment_filters(_get_appointment_queryset(), request.query_params).order_by(
            "-date",
            "start_time",
        )
        return Response(
            {
                "count": queryset.count(),
                "results": AppointmentSerializer(queryset, many=True).data,
            }
        )


class AdminAnalyticsView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        queryset = _apply_appointment_filters(_get_appointment_queryset(), request.query_params)
        total_appointments = queryset.count()
        no_show_count = queryset.filter(status=AppointmentStatus.NO_SHOW).count()
        no_show_rate = round((no_show_count / total_appointments) * 100, 2) if total_appointments else 0.0

        peak_hours = [
            {"time": row["start_time"], "count": row["count"]}
            for row in queryset.values("start_time").annotate(count=Count("id")).order_by("-count", "start_time")
        ]

        return Response(
            {
                "total_appointments": total_appointments,
                "no_show_count": no_show_count,
                "no_show_rate": no_show_rate,
                "peak_hours": peak_hours,
            }
        )


class AppointmentCSVExportView(APIView):
    permission_classes = [IsAdmin]

    def get(self, request):
        queryset = _apply_appointment_filters(_get_appointment_queryset(), request.query_params).order_by(
            "-date",
            "start_time",
        )

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = (
            f'attachment; filename="appointments-{timezone.localdate().isoformat()}.csv"'
        )

        writer = csv.writer(response)
        writer.writerow(
            [
                "Appointment ID",
                "Patient Name",
                "Patient Username",
                "Doctor Username",
                "Date",
                "Start Time",
                "End Time",
                "Status",
                "Check In Time",
            ]
        )

        for appointment in queryset:
            consultation_record = getattr(appointment, "consultation_record", None)
            writer.writerow(
                [
                    appointment.id,
                    appointment.patient.user.get_full_name().strip() or appointment.patient.user.username,
                    appointment.patient.user.username,
                    appointment.doctor.user.username,
                    appointment.date,
                    appointment.start_time,
                    appointment.end_time,
                    appointment.get_status_display(),
                    consultation_record.check_in_time if consultation_record else "",
                ]
            )

        return response


class PatientAppointmentsAPIView(APIView):
    permission_classes = [IsPatient]

    def get(self, request):
        patient = _get_patient_profile_or_none(request.user)
        if patient is None:
            return Response({"detail": "Patient profile required."}, status=status.HTTP_403_FORBIDDEN)

        today = timezone.localdate()
        current_time = timezone.localtime().time()

        upcoming = (
            patient.appointments.filter(date__gte=today)
            .exclude(status__in=[AppointmentStatus.CANCELLED, AppointmentStatus.COMPLETED, AppointmentStatus.NO_SHOW])
            .order_by("date", "start_time")
        )
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

@login_required
def check_in_local(request, appointment_id):
    if request.user.role not in {UserRole.DOCTOR, UserRole.RECEPTIONIST}:
        messages.error(request, "You do not have permission to check in appointments.")
        return redirect('dashboard_redirect')

    appointment = get_object_or_404(Appointment, id=appointment_id)

    if request.user.role == UserRole.DOCTOR:
        doctor_profile = get_object_or_404(DoctorProfile, user=request.user)
        if appointment.doctor_id != doctor_profile.id:
            messages.error(request, "You can only check in your own appointments.")
            return redirect('doctor_queue')

    if appointment.date != timezone.localdate():
        messages.error(request, "Only today's appointments can be checked in.")
        return redirect('doctor_queue' if request.user.role == UserRole.DOCTOR else 'receptionist_dashboard')

    if appointment.status in [
        AppointmentStatus.CANCELLED,
        AppointmentStatus.DECLINED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW
    ]:
        messages.error(request, "This appointment cannot be checked in.")
        return redirect('doctor_queue' if request.user.role == UserRole.DOCTOR else 'receptionist_dashboard')

    appointment.status = AppointmentStatus.CHECKED_IN
    appointment.save(update_fields=['status'])

    # create consultation record
    ConsultationRecord.objects.update_or_create(
        appointment=appointment,
        defaults={"check_in_time": timezone.now()}
    )

    messages.success(request, "Patient checked in successfully.")
    return redirect('doctor_queue' if request.user.role == UserRole.DOCTOR else 'receptionist_dashboard')

@login_required
@role_required(UserRole.RECEPTIONIST)
def receptionist_reschedule_appointment(request, appointment_id):
    appointment = get_object_or_404(
        Appointment.objects.select_related(
            "doctor__user",
            "patient__user"
        ),
        id=appointment_id
    )

    if appointment.status in [
        AppointmentStatus.CANCELLED,
        AppointmentStatus.COMPLETED,
        AppointmentStatus.NO_SHOW,
        AppointmentStatus.DECLINED,
    ]:
        messages.error(request, "This appointment cannot be rescheduled.")
        return redirect("receptionist_dashboard")

    if request.method == "POST":
        date = request.POST.get("date")
        start_time = _parse_time_value(request.POST.get("start_time"))
        end_time = _parse_time_value(request.POST.get("end_time"))
        if start_time is None or end_time is None:
            start_time, end_time = _parse_slot_value(request.POST.get("slot"))
        reason = (request.POST.get("reason") or "").strip()

        if not date or not start_time or not end_time:
            messages.error(request, "Please choose a valid slot.")
            return redirect("receptionist_reschedule_appointment", appointment_id=appointment.id)

        parsed_date = datetime.strptime(date, "%Y-%m-%d").date()
        old_date = appointment.date
        old_start_time = appointment.start_time
        old_end_time = appointment.end_time

        _, error_code = _book_or_reschedule_appointment(
            doctor=appointment.doctor,
            patient=appointment.patient,
            date=parsed_date,
            start_time=start_time,
            end_time=end_time,
            existing_appointment=appointment,
        )

        if error_code is None:
            _create_reschedule_record(
                appointment=appointment,
                changed_by=request.user,
                old_date=old_date,
                old_start_time=old_start_time,
                old_end_time=old_end_time,
                new_date=parsed_date,
                new_start_time=start_time,
                new_end_time=end_time,
                reason=reason,
            )

        if error_code == "future_only":
            messages.error(request, "Appointment must be rescheduled to a future date.")
            return redirect(
                f"{reverse('receptionist_reschedule_appointment', args=[appointment.id])}?date={date}"
            )

        if error_code == "conflict":
            messages.error(request, "This slot conflicts with another appointment.")
            return redirect(
                f"{reverse('receptionist_reschedule_appointment', args=[appointment.id])}?date={date}"
            )

        messages.success(request, "Appointment rescheduled successfully.")
        return redirect("receptionist_dashboard")

    context, error_message = _build_receptionist_reschedule_context(
        appointment,
        request.GET.get("date"),
    )
    if context is None:
        messages.error(request, error_message)
        return redirect("receptionist_dashboard")

    return render(request, "appointments/doctor_slots.html", context)