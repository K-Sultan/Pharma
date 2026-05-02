from datetime import datetime, timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import DoctorProfile, DoctorScheduleException, DoctorScheduleExceptionType, PatientProfile, UserRole, Weekday, DoctorWeeklySchedule
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

	def test_receptionist_can_save_buffer_and_schedule_times_must_use_half_hours(self):
		self.client.force_login(self.receptionist_user)

		invalid_response = self.client.post(
			reverse('receptionist_doctor_schedule', args=[self.doctor.id]),
			{
				'action': 'save_weekly',
				'selected_day': Weekday.MONDAY,
				'start_time': '08:10',
				'end_time': '14:10',
			},
		)

		self.assertEqual(invalid_response.status_code, 200)
		self.assertContains(invalid_response, 'Weekly schedule times must be on 30-minute boundaries.')
		self.assertFalse(DoctorWeeklySchedule.objects.filter(doctor=self.doctor, day=Weekday.MONDAY).exists())

		invalid_buffer_response = self.client.post(
			reverse('receptionist_doctor_schedule', args=[self.doctor.id]),
			{
				'action': 'save_buffer',
				'selected_day': Weekday.MONDAY,
				'buffer_minutes': '7',
			},
		)

		self.assertEqual(invalid_buffer_response.status_code, 200)
		self.assertContains(invalid_buffer_response, 'Buffer time must be a multiple of 5 minutes between 5 and 30.')
		self.doctor.refresh_from_db()
		self.assertEqual(self.doctor.buffer_minutes, 5)

		buffer_response = self.client.post(
			reverse('receptionist_doctor_schedule', args=[self.doctor.id]),
			{
				'action': 'save_buffer',
				'selected_day': Weekday.MONDAY,
				'buffer_minutes': '10',
			},
		)

		self.assertEqual(buffer_response.status_code, 302)
		self.doctor.refresh_from_db()
		self.assertEqual(self.doctor.buffer_minutes, 10)


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

		self.assertContains(response, "Today's Appointments")
		self.assertContains(response, 'Waiting Time:')
		self.assertContains(response, '02:00:')

	def test_doctor_can_mark_no_show_from_today_page(self):
		appointment = Appointment.objects.create(
			doctor=self.doctor,
			patient=self.patient,
			date=timezone.localdate(),
			start_time=datetime.strptime('10:00', '%H:%M').time(),
			end_time=datetime.strptime('10:30', '%H:%M').time(),
			status=AppointmentStatus.CONFIRMED,
		)

		self.client.force_login(self.doctor_user)

		response = self.client.post(reverse('mark_no_show_local', args=[appointment.id]))

		self.assertEqual(response.status_code, 302)
		appointment.refresh_from_db()
		self.assertEqual(appointment.status, AppointmentStatus.NO_SHOW)

	def test_doctor_can_check_in_from_today_page(self):
		appointment = Appointment.objects.create(
			doctor=self.doctor,
			patient=self.patient,
			date=timezone.localdate(),
			start_time=datetime.strptime('11:00', '%H:%M').time(),
			end_time=datetime.strptime('11:30', '%H:%M').time(),
			status=AppointmentStatus.CONFIRMED,
		)

		self.client.force_login(self.doctor_user)

		response = self.client.post(reverse('check_in_local', args=[appointment.id]))

		self.assertEqual(response.status_code, 302)
		appointment.refresh_from_db()
		self.assertEqual(appointment.status, AppointmentStatus.CHECKED_IN)

	def test_receptionist_dashboard_shows_waiting_time(self):
		self.client.force_login(self.receptionist_user)

		response = self.client.get(reverse('receptionist_dashboard'))

		self.assertContains(response, "Today's Appointments")
		self.assertContains(response, 'Waiting Time:')
		self.assertContains(response, '02:00:')

	def test_receptionist_can_mark_no_show_from_today_page(self):
		appointment = Appointment.objects.create(
			doctor=self.doctor,
			patient=self.patient,
			date=timezone.localdate(),
			start_time=datetime.strptime('10:30', '%H:%M').time(),
			end_time=datetime.strptime('11:00', '%H:%M').time(),
			status=AppointmentStatus.CONFIRMED,
		)

		self.client.force_login(self.receptionist_user)

		response = self.client.post(reverse('mark_no_show_local', args=[appointment.id]))

		self.assertEqual(response.status_code, 302)
		appointment.refresh_from_db()
		self.assertEqual(appointment.status, AppointmentStatus.NO_SHOW)


class AdminAnalyticsAndExportTests(TestCase):
	def setUp(self):
		self.admin_user = User.objects.create_user(
			username='admin1',
			email='admin1@example.com',
			password='pass12345',
			role=UserRole.ADMIN,
		)
		self.doctor_user = User.objects.create_user(
			username='doctor3',
			email='doctor3@example.com',
			password='pass12345',
			role=UserRole.DOCTOR,
		)
		self.patient_user = User.objects.create_user(
			username='patient3',
			email='patient3@example.com',
			password='pass12345',
			role=UserRole.PATIENT,
		)
		self.doctor = DoctorProfile.objects.create(
			user=self.doctor_user,
			license_number='LIC-300',
			specialization='Dermatology',
			department='Outpatient',
		)
		self.patient = PatientProfile.objects.create(
			user=self.patient_user,
			phone='123456789',
			address='123 Health Street',
			emergency_contact='Emergency Contact',
		)
		DoctorWeeklySchedule.objects.create(
			doctor=self.doctor,
			day=Weekday.MONDAY,
			start_time=datetime.strptime('08:00', '%H:%M').time(),
			end_time=datetime.strptime('12:00', '%H:%M').time(),
		)
		DoctorScheduleException.objects.create(
			doctor=self.doctor,
			date=timezone.localdate() + timedelta(days=5),
			exception_type=DoctorScheduleExceptionType.UNAVAILABLE,
			note='Annual leave',
		)
		self.appointment = Appointment.objects.create(
			doctor=self.doctor,
			patient=self.patient,
			date=timezone.localdate(),
			start_time=datetime.strptime('10:00', '%H:%M').time(),
			end_time=datetime.strptime('10:30', '%H:%M').time(),
			status=AppointmentStatus.CHECKED_IN,
		)
		ConsultationRecord.objects.create(
			appointment=self.appointment,
			check_in_time=timezone.now() - timedelta(minutes=45),
		)

	def test_admin_analytics_page_shows_summary(self):
		self.client.force_login(self.admin_user)

		response = self.client.get(reverse('admin_analytics'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Analytics')
		self.assertContains(response, 'Total Appointments')
		self.assertContains(response, '1')
		self.assertContains(response, 'Checked In')

	def test_appointments_csv_export_contains_appointment_data(self):
		self.client.force_login(self.admin_user)

		response = self.client.get(reverse('admin_export_appointments_csv'))

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response['Content-Type'], 'text/csv')
		self.assertContains(response, 'Appointment ID,Date,Start Time,End Time,Status,Created At')
		self.assertContains(response, str(self.appointment.id))
		self.assertContains(response, self.patient.user.username)
		self.assertContains(response, self.doctor.user.username)

	def test_patients_csv_export_contains_patient_records(self):
		self.client.force_login(self.admin_user)

		response = self.client.get(reverse('admin_export_patients_csv'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Patient ID,Username,Name,Email,Role,Date of Birth')
		self.assertContains(response, self.patient.user.username)
		self.assertContains(response, self.patient.phone)
		self.assertContains(response, self.patient.address)

	def test_doctors_csv_export_contains_schedule_data(self):
		self.client.force_login(self.admin_user)

		response = self.client.get(reverse('admin_export_doctors_csv'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Doctor ID,Username,Name,Email,License Number,Specialization,Department,Schedule Type')
		self.assertContains(response, self.doctor.user.username)
		self.assertContains(response, 'weekly')
		self.assertContains(response, 'Monday')
		self.assertContains(response, 'exception')
		self.assertContains(response, 'Vacation / Day Off')
