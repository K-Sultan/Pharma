from django.conf import settings
from django.contrib.auth.models import AbstractUser, UserManager
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone


def _validate_buffer_multiple(value):
	if value % 5 != 0:
		raise ValidationError('Buffer time must be a multiple of 5 minutes.')


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
	buffer_minutes = models.PositiveSmallIntegerField(
		default=5,
		validators=[MinValueValidator(5), MaxValueValidator(30), _validate_buffer_multiple],
		help_text='Buffer time between slots in minutes.',
	)

	def clean(self):
		super().clean()
		if self.buffer_minutes is not None and self.buffer_minutes % 5 != 0:
			raise ValidationError({'buffer_minutes': 'Buffer time must be a multiple of 5 minutes.'})

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


class Weekday(models.IntegerChoices):
	MONDAY = 0, 'Monday'
	TUESDAY = 1, 'Tuesday'
	WEDNESDAY = 2, 'Wednesday'
	THURSDAY = 3, 'Thursday'
	FRIDAY = 4, 'Friday'
	SATURDAY = 5, 'Saturday'
	SUNDAY = 6, 'Sunday'


def _validate_half_hour_boundary(value):
	if value.minute not in {0, 30} or value.second or value.microsecond:
		raise ValidationError('Weekly schedule times must be on 30-minute boundaries.')

class DoctorWeeklySchedule(models.Model):
	doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='weekly_schedule')
	day = models.IntegerField(choices=Weekday.choices)
	start_time = models.TimeField()
	end_time = models.TimeField()

	class Meta:
		ordering = ['doctor', 'day', 'start_time']
		constraints = [
			models.UniqueConstraint(fields=['doctor', 'day'], name='unique_doctor_weekday_schedule'),
		]

	def clean(self):
		super().clean()
		# Let field-level validation report missing values.
		if self.start_time is None or self.end_time is None:
			return
		if self.start_time >= self.end_time:
			raise ValidationError('Weekly schedule start time must be earlier than end time.')
		_validate_half_hour_boundary(self.start_time)
		_validate_half_hour_boundary(self.end_time)

	def __str__(self):
		return f'{self.doctor.user.username} - {self.get_day_display()} {self.start_time} to {self.end_time}'


class DoctorScheduleExceptionType(models.TextChoices):
	UNAVAILABLE = 'unavailable', 'Vacation / Day Off'
	AVAILABLE = 'available', 'One-off Working Day'


class DoctorScheduleException(models.Model):
	doctor = models.ForeignKey(DoctorProfile, on_delete=models.CASCADE, related_name='schedule_exceptions')
	date = models.DateField()
	exception_type = models.CharField(max_length=20, choices=DoctorScheduleExceptionType.choices)
	start_time = models.TimeField(blank=True, null=True)
	end_time = models.TimeField(blank=True, null=True)
	note = models.CharField(max_length=255, blank=True)

	class Meta:
		ordering = ['doctor', 'date', 'start_time']
		constraints = [
			models.UniqueConstraint(
				fields=['doctor', 'date'],
				name='unique_doctor_schedule_exception',
			),
		]

	def clean(self):
		super().clean()
		if self.date and self.date < timezone.localdate():
			raise ValidationError('Date cannot be in the past.')

		if self.doctor_id and self.date:
			conflict_exists = DoctorScheduleException.objects.filter(
				doctor=self.doctor,
				date=self.date,
			).exclude(pk=self.pk).exists()
			if conflict_exists:
				raise ValidationError('An exception already exists for this date.')

		if self.exception_type not in {
			DoctorScheduleExceptionType.UNAVAILABLE,
			DoctorScheduleExceptionType.AVAILABLE,
		}:
			return

		if self.exception_type == DoctorScheduleExceptionType.UNAVAILABLE:
			if self.start_time or self.end_time:
				raise ValidationError('Vacation/day-off entries must not include working hours.')
			return

		if not self.start_time or not self.end_time:
			raise ValidationError('One-off working day requires both start and end times.')
		if self.start_time >= self.end_time:
			raise ValidationError('One-off working day start time must be earlier than end time.')

	def __str__(self):
		return f'{self.doctor.user.username} - {self.date} ({self.get_exception_type_display()})'
