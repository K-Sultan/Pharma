from django.urls import path
from . import views

urlpatterns = [
    path('', views.appointment_list_view, name='appointment_list'),
    path('manage/', views.appointments_hub, name='appointments_hub'),

    path("doctors/", views.doctor_list, name="doctor_list"),
    path("doctors/<int:doctor_id>/", views.doctor_slots, name="doctor_slots"),
    path("doctors/<int:doctor_id>/book/", views.book_appointment, name="book_appointment"),

    path("appointments/", views.patient_appointments, name="patient_appointments"),
    path("appointments/<int:appointment_id>/reschedule/", views.reschedule_appointment, name="reschedule_appointment"),
    path("appointments/<int:appointment_id>/receptionist-reschedule/", views.receptionist_reschedule_appointment, name="receptionist_reschedule_appointment"),
    path("appointments/<int:appointment_id>/cancel/", views.cancel_appointment, name="cancel_appointment"),
    path("appointments/<int:appointment_id>/check-in/", views.check_in_local, name="check_in_local"),
    path("appointments/<int:appointment_id>/staff-status/", views.staff_appointment_status_update, name="staff_appointment_status_update"),

    path("api/", views.AppointmentApiRootView.as_view(), name="appointment_api_root"),
    path("api/doctors/", views.DoctorListAPIView.as_view(), name="doctor_list_api"),
    path("api/doctors/<int:doctor_id>/", views.DoctorSlotsAPIView.as_view(), name="doctor_slots_api"),
    path("api/doctors/<int:doctor_id>/queue/", views.DoctorDailyQueueAPIView.as_view(), name="doctor_daily_queue_api"),
    path("api/doctors/<int:doctor_id>/book/", views.BookAppointmentAPIView.as_view(), name="book_appointment_api"),
    path("api/appointments/", views.PatientAppointmentsAPIView.as_view(), name="patient_appointments_api"),
    path("api/appointments/search/", views.AppointmentSearchAPIView.as_view(), name="appointment_search_api"),
    path("api/appointments/export/csv/", views.AppointmentCSVExportView.as_view(), name="appointment_csv_export_api"),
    path("api/appointments/<int:appointment_id>/reschedule/", views.RescheduleAppointmentAPIView.as_view(), name="reschedule_appointment_api"),
    path("api/appointments/<int:appointment_id>/cancel/", views.CancelAppointmentAPIView.as_view(), name="cancel_appointment_api"),
    path("api/appointments/<int:appointment_id>/check-in/", views.AppointmentCheckInAPIView.as_view(), name="appointment_check_in_api"),
    path("api/appointments/<int:appointment_id>/status/", views.AppointmentStatusUpdateAPIView.as_view(), name="appointment_status_update_api"),
    path("api/admin/analytics/", views.AdminAnalyticsView.as_view(), name="appointment_admin_analytics_api"),
]