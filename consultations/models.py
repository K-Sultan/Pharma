from django.db import models
from appointments.models import Appointment

class ConsultationRecord(models.Model):
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name="consultation_record",
        blank=True,
        null=True,
    )
    check_in_time = models.DateTimeField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True, help_text="General notes from the consultation")
    diagnosis = models.TextField(blank=True, null=True, help_text="Final or provisional diagnosis")
    requested_tests = models.TextField(blank=True, null=True, help_text="Tests requested by the doctor")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        if self.appointment_id:
            return f"Consultation Record for Appointment #{self.appointment_id}"
        return f"Consultation Record #{self.id}"


class PrescriptionItem(models.Model):
    """
    Represents a single drug prescription within a consultation record.
    """
    consultation = models.ForeignKey(ConsultationRecord, on_delete=models.CASCADE, related_name='prescriptions')
    drug = models.CharField(max_length=255, help_text="Name of the drug")
    dose = models.CharField(max_length=255, help_text="Dosage instructions (e.g., '1 pill every 8 hours')")
    duration = models.CharField(max_length=255, help_text="Duration of the prescription (e.g., '7 days')")

    def __str__(self):
        return f"{self.drug} - {self.dose} for {self.duration}"
