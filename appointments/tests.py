from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import DoctorProfile, PatientProfile, UserRole
from .models import Appointment, AppointmentReschedule, AppointmentStatus
from accounts.models import DoctorWeeklySchedule


User = get_user_model()


class AppointmentRescheduleTests(TestCase):
	def setUp(self):
		self.patient_user = User.objects.create_user(
			username="patient1",
			email="patient1@example.com",
			password="pass12345",
			role=UserRole.PATIENT,
		)
		self.doctor_user = User.objects.create_user(
			username="doctor1",
			email="doctor1@example.com",
			password="pass12345",
			role=UserRole.DOCTOR,
		)
		self.patient = PatientProfile.objects.create(user=self.patient_user)
		self.doctor = DoctorProfile.objects.create(
			user=self.doctor_user,
			license_number="LIC-001",
			specialization="General Medicine",
		)
		self.appointment = Appointment.objects.create(
			doctor=self.doctor,
			patient=self.patient,
			date=timezone.localdate() + timedelta(days=2),
			start_time=datetime.strptime("09:00", "%H:%M").time(),
			end_time=datetime.strptime("09:30", "%H:%M").time(),
			status=AppointmentStatus.CONFIRMED,
		)

	def _next_weekday_date(self):
		target = timezone.localdate() + timedelta(days=1)
		while target.weekday() != self.appointment.date.weekday():
			target += timedelta(days=1)
		return target

	def test_reschedule_creates_history_record_with_optional_reason(self):
		self.client.force_login(self.patient_user)

		response = self.client.post(
			reverse("reschedule_appointment", args=[self.appointment.id]),
			{
				"date": (timezone.localdate() + timedelta(days=3)).isoformat(),
				"start_time": "10:00:00",
				"end_time": "10:30:00",
				"reason": "",
			},
		)

		self.assertEqual(response.status_code, 302)
		self.appointment.refresh_from_db()
		self.assertEqual(AppointmentReschedule.objects.count(), 1)
		reschedule = AppointmentReschedule.objects.get()
		self.assertEqual(reschedule.appointment, self.appointment)
		self.assertEqual(reschedule.reason, "")
		self.assertEqual(reschedule.old_date, timezone.localdate() + timedelta(days=2))
		self.assertEqual(reschedule.changed_by, self.patient_user)

	def test_doctor_slots_preserves_reschedule_context_and_single_reason_field(self):
		DoctorWeeklySchedule.objects.create(
			doctor=self.doctor,
			day=self.appointment.date.weekday(),
			start_time=datetime.strptime("09:00", "%H:%M").time(),
			end_time=datetime.strptime("11:00", "%H:%M").time(),
		)
		self.client.force_login(self.patient_user)

		response = self.client.get(
			reverse("doctor_slots", args=[self.doctor.id]),
			{
				"appointment": self.appointment.id,
				"date": self.appointment.date.isoformat(),
			},
		)

		self.assertContains(response, f'name="appointment" value="{self.appointment.id}"', html=False)
		self.assertEqual(response.content.decode().count('name="reason"'), 1)


class StaffAppointmentManagementTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			username="admin1",
			email="admin1@example.com",
			password="pass12345",
			role=UserRole.ADMIN,
		)
		self.receptionist_user = User.objects.create_user(
			username="reception1",
			email="reception1@example.com",
			password="pass12345",
			role=UserRole.RECEPTIONIST,
		)
		self.patient_user = User.objects.create_user(
			username="patient2",
			email="patient2@example.com",
			password="pass12345",
			role=UserRole.PATIENT,
		)
		self.overdue_patient_user = User.objects.create_user(
			username="patient3",
			email="patient3@example.com",
			password="pass12345",
			role=UserRole.PATIENT,
		)
		self.doctor_user = User.objects.create_user(
			username="doctor2",
			email="doctor2@example.com",
			password="pass12345",
			role=UserRole.DOCTOR,
		)
		self.admin_profile = PatientProfile.objects.create(user=self.admin_user)
		self.receptionist_profile = PatientProfile.objects.create(user=self.receptionist_user)
		self.patient = PatientProfile.objects.create(user=self.patient_user)
		self.overdue_patient = PatientProfile.objects.create(user=self.overdue_patient_user)
		self.doctor = DoctorProfile.objects.create(
			user=self.doctor_user,
			license_number="LIC-002",
			specialization="General Medicine",
		)
		self.pending_appointment = Appointment.objects.create(
			doctor=self.doctor,
			patient=self.patient,
			date=timezone.localdate() + timedelta(days=1),
			start_time=datetime.strptime("11:00", "%H:%M").time(),
			end_time=datetime.strptime("11:30", "%H:%M").time(),
			status=AppointmentStatus.PENDING,
		)
		self.confirmed_appointment = Appointment.objects.create(
			doctor=self.doctor,
			patient=self.patient,
			date=timezone.localdate(),
			start_time=datetime.strptime("12:00", "%H:%M").time(),
			end_time=datetime.strptime("12:30", "%H:%M").time(),
			status=AppointmentStatus.CONFIRMED,
		)
		self.checked_in_appointment = Appointment.objects.create(
			doctor=self.doctor,
			patient=self.patient,
			date=timezone.localdate(),
			start_time=datetime.strptime("12:45", "%H:%M").time(),
			end_time=datetime.strptime("13:00", "%H:%M").time(),
			status=AppointmentStatus.CHECKED_IN,
		)
		self.declined_appointment = Appointment.objects.create(
			doctor=self.doctor,
			patient=self.patient,
			date=timezone.localdate() + timedelta(days=2),
			start_time=datetime.strptime("13:00", "%H:%M").time(),
			end_time=datetime.strptime("13:30", "%H:%M").time(),
			status=AppointmentStatus.DECLINED,
		)
		self.overdue_pending_appointment = Appointment.objects.create(
			doctor=self.doctor,
			patient=self.overdue_patient,
			date=timezone.localdate() - timedelta(days=1),
			start_time=datetime.strptime("08:00", "%H:%M").time(),
			end_time=datetime.strptime("08:30", "%H:%M").time(),
			status=AppointmentStatus.PENDING,
		)

	def test_staff_hub_shows_pending_tab_and_actions(self):
		self.client.force_login(self.receptionist_user)

		response = self.client.get(reverse("appointments_hub"))

		self.assertContains(response, "Manage Appointments")
		self.assertContains(response, "Pending (1)")
		self.assertContains(response, "Confirm")
		self.assertContains(response, "Decline")
		self.assertContains(response, self.pending_appointment.patient.user.username)

	def test_overdue_pending_appointments_become_no_show(self):
		self.client.force_login(self.admin_user)

		response = self.client.get(reverse("appointments_hub"), {"tab": "pending"})

		self.assertEqual(response.status_code, 200)
		self.overdue_pending_appointment.refresh_from_db()
		self.assertEqual(self.overdue_pending_appointment.status, AppointmentStatus.NO_SHOW)
		self.assertNotContains(response, f"Appointment #{self.overdue_pending_appointment.id}")

		no_show_response = self.client.get(reverse("appointments_hub"), {"tab": "no_show"})
		self.assertContains(no_show_response, "No Show")
		self.assertContains(no_show_response, f"Appointment #{self.overdue_pending_appointment.id}")

	def test_staff_can_confirm_and_decline_pending_appointments(self):
		self.client.force_login(self.admin_user)

		confirm_response = self.client.post(
			reverse("staff_appointment_status_update", args=[self.pending_appointment.id]),
			{"action": "confirm", "tab": "pending"},
		)
		self.assertEqual(confirm_response.status_code, 302)
		self.pending_appointment.refresh_from_db()
		self.assertEqual(self.pending_appointment.status, AppointmentStatus.CONFIRMED)

		decline_response = self.client.post(
			reverse("staff_appointment_status_update", args=[self.confirmed_appointment.id]),
			{"action": "decline", "tab": "confirmed"},
		)
		self.assertEqual(decline_response.status_code, 302)
		self.confirmed_appointment.refresh_from_db()
		self.assertEqual(self.confirmed_appointment.status, AppointmentStatus.DECLINED)

	def test_staff_hub_searches_by_appointment_id(self):
		self.client.force_login(self.receptionist_user)

		response = self.client.get(
			reverse("appointments_hub"),
			{"tab": "all", "search": str(self.pending_appointment.id)},
		)

		self.assertContains(response, f"Appointment #{self.pending_appointment.id}")
		self.assertNotContains(response, f"Appointment #{self.confirmed_appointment.id}")

	def test_staff_hub_shows_checked_in_tab(self):
		self.client.force_login(self.receptionist_user)

		response = self.client.get(reverse("appointments_hub"), {"tab": "checked_in"})

		self.assertContains(response, "Check-In")
		self.assertContains(response, f"Appointment #{self.checked_in_appointment.id}")
		self.assertContains(response, "Checked In")

	def test_staff_hub_filters_by_date_doctor_and_patient(self):
		other_doctor_user = User.objects.create_user(
			username="doctor3",
			email="doctor3@example.com",
			password="pass12345",
			role=UserRole.DOCTOR,
		)
		other_patient_user = User.objects.create_user(
			username="patient4",
			email="patient4@example.com",
			password="pass12345",
			role=UserRole.PATIENT,
		)
		other_doctor = DoctorProfile.objects.create(
			user=other_doctor_user,
			license_number="LIC-003",
			specialization="Pediatrics",
		)
		other_patient = PatientProfile.objects.create(user=other_patient_user)
		filtered_date = timezone.localdate() + timedelta(days=4)
		matching_appointment = Appointment.objects.create(
			doctor=other_doctor,
			patient=other_patient,
			date=filtered_date,
			start_time=datetime.strptime("15:00", "%H:%M").time(),
			end_time=datetime.strptime("15:30", "%H:%M").time(),
			status=AppointmentStatus.CONFIRMED,
		)

		self.client.force_login(self.receptionist_user)

		response = self.client.get(
			reverse("appointments_hub"),
			{
				"tab": "all",
				"start_date": filtered_date.isoformat(),
				"end_date": filtered_date.isoformat(),
				"doctor_id": other_doctor.id,
				"patient_id": other_patient.id,
			},
		)

		self.assertContains(response, f"Appointment #{matching_appointment.id}")
		self.assertContains(response, other_patient.user.username)
		self.assertContains(response, other_doctor.user.username)
		self.assertNotContains(response, f"Appointment #{self.pending_appointment.id}")
		self.assertNotContains(response, f"Appointment #{self.confirmed_appointment.id}")

	def test_receptionist_reschedule_uses_shared_page_and_creates_history(self):
		DoctorWeeklySchedule.objects.create(
			doctor=self.doctor,
			day=self.pending_appointment.date.weekday(),
			start_time=datetime.strptime("11:00", "%H:%M").time(),
			end_time=datetime.strptime("12:00", "%H:%M").time(),
		)
		self.client.force_login(self.receptionist_user)

		response = self.client.get(
			reverse("receptionist_reschedule_appointment", args=[self.pending_appointment.id]),
			{"date": self.pending_appointment.date.isoformat()},
		)

		self.assertTemplateUsed(response, "appointments/doctor_slots.html")
		self.assertContains(response, f'name="appointment" value="{self.pending_appointment.id}"', html=False)
		self.assertEqual(response.content.decode().count('name="reason"'), 1)

		post_response = self.client.post(
			reverse("receptionist_reschedule_appointment", args=[self.pending_appointment.id]),
			{
				"date": self.pending_appointment.date.isoformat(),
				"slot": "11:30:00|12:00:00",
				"reason": "Coverage change",
			},
		)

		self.assertEqual(post_response.status_code, 302)
		self.pending_appointment.refresh_from_db()
		reschedule = AppointmentReschedule.objects.get(appointment=self.pending_appointment)
		self.assertEqual(reschedule.changed_by, self.receptionist_user)
		self.assertEqual(reschedule.reason, "Coverage change")

	def test_doctor_queue_lists_confirmed_appointments(self):
		self.client.force_login(self.doctor_user)

		response = self.client.get(reverse("doctor_queue"))

		self.assertContains(response, "Today Confirmed Queue")
		self.assertContains(response, self.confirmed_appointment.patient.user.get_full_name() or self.confirmed_appointment.patient.user.username)
