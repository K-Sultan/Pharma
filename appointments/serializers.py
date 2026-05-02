from django.utils import timezone
from rest_framework import serializers

from accounts.models import DoctorProfile
from .models import Appointment, AppointmentStatus


class DoctorProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = DoctorProfile
        fields = ["id", "username", "specialization", "department", "bio", "buffer_minutes"]


class AppointmentSerializer(serializers.ModelSerializer):
    doctor = DoctorProfileSerializer(read_only=True)
    patient_username = serializers.CharField(source="patient.user.username", read_only=True)
    patient_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    check_in_time = serializers.DateTimeField(source="consultation_record.check_in_time", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "doctor",
            "patient_username",
            "patient_name",
            "date",
            "start_time",
            "end_time",
            "status",
            "status_display",
            "check_in_time",
            "created_at",
        ]

    def get_patient_name(self, obj):
        full_name = obj.patient.user.get_full_name().strip()
        return full_name or obj.patient.user.username


class AppointmentQueueSerializer(AppointmentSerializer):
    waiting_time = serializers.SerializerMethodField()

    class Meta(AppointmentSerializer.Meta):
        fields = AppointmentSerializer.Meta.fields + ["waiting_time"]

    def get_waiting_time(self, obj):
        consultation_record = getattr(obj, "consultation_record", None)
        if not consultation_record or not consultation_record.check_in_time:
            return None

        elapsed = max(int((timezone.now() - consultation_record.check_in_time).total_seconds()), 0)
        hours, remainder = divmod(elapsed, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


class AppointmentStatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(
        choices=[
            AppointmentStatus.COMPLETED,
            AppointmentStatus.NO_SHOW,
        ]
    )


class AppointmentSlotSerializer(serializers.Serializer):
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True, max_length=1000)
