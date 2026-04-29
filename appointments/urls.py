from django.urls import path
from . import views

urlpatterns = [
    path('', views.appointment_list_view, name='appointment_list'),
    path("doctors/", views.doctor_list, name="doctor_list"),
    path("doctors/<int:doctor_id>/", views.doctor_slots, name="doctor_slots"),
    path("doctors/<int:doctor_id>/book/", views.book_appointment, name="book_appointment"),
    path("appointments/<int:appointment_id>/reschedule/", views.reschedule_appointment, name="reschedule_appointment"),
    path("appointments/<int:appointment_id>/cancel/", views.cancel_appointment, name="cancel_appointment"),
    path("appointments/", views.patient_appointments, name="patient_appointments"),
    path("api/", views.AppointmentApiRootView.as_view(), name="appointment_api_root"),
    path("api/doctors/", views.DoctorListAPIView.as_view(), name="doctor_list_api"),
    path("api/doctors/<int:doctor_id>/", views.DoctorSlotsAPIView.as_view(), name="doctor_slots_api"),
    path("api/doctors/<int:doctor_id>/book/", views.BookAppointmentAPIView.as_view(), name="book_appointment_api"),
    path("api/appointments/<int:appointment_id>/reschedule/", views.RescheduleAppointmentAPIView.as_view(), name="reschedule_appointment_api"),
    path("api/appointments/<int:appointment_id>/cancel/", views.CancelAppointmentAPIView.as_view(), name="cancel_appointment_api"),
    path("api/appointments/", views.PatientAppointmentsAPIView.as_view(), name="patient_appointments_api"),
]