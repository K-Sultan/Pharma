from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html
from .models import Appointment, AppointmentReschedule

@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        'id',
        'patient',
        'doctor',
        'date',
        'start_time',
        'end_time',
        'status',
        'consultation_link',
    )
    list_filter = ('date', 'start_time', 'status', 'doctor')
    search_fields = (
        'patient__user__username',
        'patient__user__first_name',
        'patient__user__last_name',
        'doctor__user__username',
    )
    readonly_fields = ('created_at',)
    
    
    def consultation_link(self, obj):
        if hasattr(obj, 'consultation_record') and obj.consultation_record:
            url = reverse('admin:consultations_consultationrecord_change', args=[obj.consultation_record.id])
            return format_html('<a href="{}">View Consultation</a>', url)
        return 'No Consultation'
    consultation_link.short_description = 'Consultation'
    consultation_link.allow_tags = True


@admin.register(AppointmentReschedule)
class AppointmentRescheduleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "appointment",
        "old_date",
        "old_start_time",
        "old_end_time",
        "new_date",
        "new_start_time",
        "new_end_time",
        "changed_at",
    )
    list_filter = ("changed_at", "new_date", "old_date")
    search_fields = (
        "appointment__patient__user__username",
        "appointment__doctor__user__username",
        "reason",
    )

