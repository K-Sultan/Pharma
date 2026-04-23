from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard_redirect, name='dashboard_redirect'),
    path('patient/', views.patient_dashboard, name='patient_dashboard'),
    path('doctor/', views.doctor_dashboard, name='doctor_dashboard'),
    path('receptionist/', views.receptionist_dashboard, name='receptionist_dashboard'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
]