from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, DoctorProfile, PatientProfile, ReceptionistProfile


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
	fieldsets = UserAdmin.fieldsets + (
		('Clinic Role', {'fields': ('role',)}),
	)
	add_fieldsets = UserAdmin.add_fieldsets + (
		('Clinic Role', {'fields': ('role',)}),
	)
	list_display = ('username', 'email', 'role', 'is_staff', 'is_active')
	list_filter = ('role', 'is_staff', 'is_superuser', 'is_active')


@admin.register(PatientProfile)
class PatientProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'phone', 'date_of_birth')
	search_fields = ('user__username', 'user__email', 'phone')


@admin.register(DoctorProfile)
class DoctorProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'specialization', 'license_number', 'department')
	search_fields = ('user__username', 'user__email', 'license_number', 'specialization')


@admin.register(ReceptionistProfile)
class ReceptionistProfileAdmin(admin.ModelAdmin):
	list_display = ('user', 'department', 'phone_extension')
	search_fields = ('user__username', 'user__email', 'department')
