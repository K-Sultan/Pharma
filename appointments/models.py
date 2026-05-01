from django.db import models
from accounts.models import DoctorProfile, PatientProfile


class AppointmentStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    CONFIRMED = "confirmed", "Confirmed"
    DECLINED = "declined", "Declined"
    CHECKED_IN = "checked_in", "Checked In"
    COMPLETED = "completed", "Completed"
    NO_SHOW = "no_show", "No Show"
    CANCELLED = "cancelled", "Cancelled"


class Appointment(models.Model):
    doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name="appointments")
    patient = models.ForeignKey(PatientProfile, on_delete=models.CASCADE, related_name="appointments")

    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()

    status = models.CharField(
        max_length=20,
        choices=AppointmentStatus.choices,
        default=AppointmentStatus.PENDING
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "date", "start_time"],
                name="unique_doctor_slot"
            )
        ]
        ordering = ["-date", "start_time"]

    def __str__(self):
        return f"{self.patient.user.username} with {self.doctor.user.username} on {self.date} at {self.start_time}"


class AppointmentReschedule(models.Model):
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE, related_name="reschedules")

    old_date = models.DateField()
    old_start_time = models.TimeField()
    old_end_time = models.TimeField()

    new_date = models.DateField()
    new_start_time = models.TimeField()
    new_end_time = models.TimeField()

    reason = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-changed_at"]

    def __str__(self):
        return f"Reschedule for appointment #{self.appointment_id} at {self.changed_at}"
