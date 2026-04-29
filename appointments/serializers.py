from rest_framework import serializers

from accounts.models import DoctorProfile
from .models import Appointment


class DoctorProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = DoctorProfile
        fields = ["id", "username", "specialization", "department", "bio"]


class AppointmentSerializer(serializers.ModelSerializer):
    doctor = DoctorProfileSerializer(read_only=True)
    patient_username = serializers.CharField(source="patient.user.username", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "doctor",
            "patient_username",
            "date",
            "start_time",
            "end_time",
            "status",
            "status_display",
            "created_at",
        ]


class AppointmentSlotSerializer(serializers.Serializer):
    date = serializers.DateField()
    start_time = serializers.TimeField()
    end_time = serializers.TimeField()