from django.contrib import admin
from .models import Appointment, AppointmentReschedule


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "patient",
        "doctor",
        "date",
        "start_time",
        "end_time",
        "status",
    )
    list_filter = ("status", "date", "doctor")
    search_fields = (
        "patient__user__username",
        "doctor__user__username",
    )


@admin.register(AppointmentReschedule)
class AppointmentRescheduleAdmin(admin.ModelAdmin):
    list_display = (
        "appointment",
        "old_date",
        "old_start_time",
        "new_date",
        "new_start_time",
        "changed_by",
        "changed_at",
    )
    list_filter = ("changed_at",)
    search_fields = (
        "appointment__patient__user__username",
        "appointment__doctor__user__username",
        "changed_by__username",
    )