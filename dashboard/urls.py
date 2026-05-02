from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_redirect, name='dashboard_redirect'),
    path('patient/', views.patient_dashboard, name='patient_dashboard'),
    path('doctor/', views.doctor_dashboard, name='doctor_dashboard'),
    path('doctor/schedule/', views.doctor_schedule_view, name='doctor_schedule'),
    path('receptionist/', views.receptionist_dashboard, name='receptionist_dashboard'),
    path('receptionist/doctors/', views.receptionist_doctor_schedule_list, name='receptionist_doctor_schedule_list'),
    path('receptionist/doctors/<int:doctor_id>/schedule/', views.doctor_schedule_view, name='receptionist_doctor_schedule'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('doctor/queue/', views.doctor_queue_view, name='doctor_queue'),
]