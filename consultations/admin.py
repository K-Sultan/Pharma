from django.contrib import admin
from .models import ConsultationRecord, PrescriptionItem

class PrescriptionItemInline(admin.TabularInline):
    model = PrescriptionItem
    extra = 1

@admin.register(ConsultationRecord)
class ConsultationRecordAdmin(admin.ModelAdmin):
    list_display = ('id', 'appointment', 'check_in_time', 'created_at')
    list_filter = ('created_at', 'check_in_time')
    search_fields = ('appointment__patient__user__username', 'appointment__doctor__user__username')
    inlines = [PrescriptionItemInline]

@admin.register(PrescriptionItem)
class PrescriptionItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'consultation', 'drug', 'dose', 'duration')
    search_fields = ('drug',)
