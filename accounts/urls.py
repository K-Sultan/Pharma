from django.urls import path
from . import views

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('staff/create-doctor/', views.create_doctor_view, name='create_doctor'),
    path('staff/create-receptionist/', views.create_receptionist_view, name='create_receptionist'),
]