from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.db import models


class UserRole(models.TextChoices):
	PATIENT = 'patient', 'Patient'
	DOCTOR = 'doctor', 'Doctor'
	RECEPTIONIST = 'receptionist', 'Receptionist'
	ADMIN = 'admin', 'Admin'


class CustomUserManager(UserManager):
	def create_user(self, username, email=None, password=None, **extra_fields):
		extra_fields.setdefault('role', UserRole.PATIENT)
		return super().create_user(username, email=email, password=password, **extra_fields)

	def create_superuser(self, username, email=None, password=None, **extra_fields):
		extra_fields.setdefault('is_staff', True)
		extra_fields.setdefault('is_superuser', True)
		extra_fields.setdefault('role', UserRole.ADMIN)

		if extra_fields.get('is_staff') is not True:
			raise ValueError('Superuser must have is_staff=True.')
		if extra_fields.get('is_superuser') is not True:
			raise ValueError('Superuser must have is_superuser=True.')

		return super().create_superuser(username, email=email, password=password, **extra_fields)


class CustomUser(AbstractUser):
	email = models.EmailField(unique=True)
	role = models.CharField(max_length=20, choices=UserRole.choices, default=UserRole.PATIENT, db_index=True)

	objects = CustomUserManager()

	def clean(self):
		super().clean()
		if self.role == UserRole.ADMIN:
			self.is_staff = True

	def save(self, *args, **kwargs):
		if self.is_superuser:
			self.role = UserRole.ADMIN
			self.is_staff = True
		elif self.role == UserRole.ADMIN:
			self.is_staff = True
		super().save(*args, **kwargs)

	def __str__(self):
		return self.username


class PatientProfile(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='patient_profile')
	date_of_birth = models.DateField(blank=True, null=True)
	phone = models.CharField(max_length=20, blank=True)
	address = models.TextField(blank=True)
	emergency_contact = models.CharField(max_length=120, blank=True)

	def clean(self):
		super().clean()
		if self.user.role != UserRole.PATIENT:
			raise ValidationError('Patient profile can only be linked to users with patient role.')

	def __str__(self):
		return f'Patient profile: {self.user.username}'


class DoctorProfile(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='doctor_profile')
	license_number = models.CharField(max_length=100, unique=True)
	specialization = models.CharField(max_length=120)
	department = models.CharField(max_length=120, blank=True)
	bio = models.TextField(blank=True)

	def clean(self):
		super().clean()
		if self.user.role != UserRole.DOCTOR:
			raise ValidationError('Doctor profile can only be linked to users with doctor role.')

	def __str__(self):
		return f'Doctor profile: {self.user.username}'


class ReceptionistProfile(models.Model):
	user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='receptionist_profile')
	department = models.CharField(max_length=120, blank=True)
	phone_extension = models.CharField(max_length=10, blank=True)

	def clean(self):
		super().clean()
		if self.user.role != UserRole.RECEPTIONIST:
			raise ValidationError('Receptionist profile can only be linked to users with receptionist role.')

	def __str__(self):
		return f'Receptionist profile: {self.user.username}'
