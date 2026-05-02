from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import DoctorProfile, PatientProfile, UserRole, Weekday, DoctorWeeklySchedule
from appointments.models import Appointment, AppointmentStatus
from consultations.models import ConsultationRecord


User = get_user_model()


class ReceptionistDoctorScheduleTests(TestCase):
	def setUp(self):
		self.receptionist_user = User.objects.create_user(
			username='reception1',
			email='reception1@example.com',
			password='pass12345',
			role=UserRole.RECEPTIONIST,
		)
		self.doctor_user = User.objects.create_user(
			username='doctor1',
			email='doctor1@example.com',
			password='pass12345',
			role=UserRole.DOCTOR,
		)
		self.doctor = DoctorProfile.objects.create(
			user=self.doctor_user,
			license_number='LIC-100',
			specialization='Cardiology',
		)

	def test_receptionist_can_open_and_update_doctor_schedule(self):
		self.client.force_login(self.receptionist_user)

		list_response = self.client.get(reverse('receptionist_doctor_schedule_list'))
		self.assertEqual(list_response.status_code, 200)
		self.assertContains(list_response, 'Manage Schedule')
		self.assertContains(list_response, self.doctor.user.username)

		schedule_response = self.client.get(reverse('receptionist_doctor_schedule', args=[self.doctor.id]))
		self.assertEqual(schedule_response.status_code, 200)
		self.assertContains(schedule_response, 'Doctor Schedule')
		self.assertContains(schedule_response, 'Managing schedule for Dr.')

		save_response = self.client.post(
			reverse('receptionist_doctor_schedule', args=[self.doctor.id]),
			{
				'action': 'save_weekly',
				'selected_day': Weekday.MONDAY,
				'start_time': datetime.strptime('08:00', '%H:%M').time(),
				'end_time': datetime.strptime('14:00', '%H:%M').time(),
			},
		)

		self.assertEqual(save_response.status_code, 302)
		weekly_entry = DoctorWeeklySchedule.objects.get(doctor=self.doctor, day=Weekday.MONDAY)
		self.assertEqual(weekly_entry.start_time, datetime.strptime('08:00', '%H:%M').time())
		self.assertEqual(weekly_entry.end_time, datetime.strptime('14:00', '%H:%M').time())


class DashboardWaitingTimeTests(TestCase):
	def setUp(self):
		self.receptionist_user = User.objects.create_user(
			username='reception2',
			email='reception2@example.com',
			password='pass12345',
			role=UserRole.RECEPTIONIST,
		)
		self.doctor_user = User.objects.create_user(
			username='doctor2',
			email='doctor2@example.com',
			password='pass12345',
			role=UserRole.DOCTOR,
		)
		self.patient_user = User.objects.create_user(
			username='patient2',
			email='patient2@example.com',
			password='pass12345',
			role=UserRole.PATIENT,
		)
		self.doctor = DoctorProfile.objects.create(
			user=self.doctor_user,
			license_number='LIC-200',
			specialization='General Medicine',
		)
		self.patient = PatientProfile.objects.create(user=self.patient_user)
		self.appointment = Appointment.objects.create(
			doctor=self.doctor,
			patient=self.patient,
			date=timezone.localdate(),
			start_time=datetime.strptime('09:00', '%H:%M').time(),
			end_time=datetime.strptime('09:30', '%H:%M').time(),
			status=AppointmentStatus.CHECKED_IN,
		)
		ConsultationRecord.objects.create(
			appointment=self.appointment,
			check_in_time=timezone.now() - timedelta(hours=2),
		)

	def test_doctor_queue_shows_waiting_time(self):
		self.client.force_login(self.doctor_user)

		response = self.client.get(reverse('doctor_queue'))

		self.assertContains(response, 'Waiting Time:')
		self.assertContains(response, '02:00:')

	def test_receptionist_dashboard_shows_waiting_time(self):
		self.client.force_login(self.receptionist_user)

		response = self.client.get(reverse('receptionist_dashboard'))

		self.assertContains(response, 'Waiting Time:')
		self.assertContains(response, '02:00:')
