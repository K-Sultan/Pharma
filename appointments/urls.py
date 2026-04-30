from django.urls import path
from . import views

urlpatterns = [
    path('', views.appointment_list_view, name='appointment_list'),

    path('doctors/', views.doctor_list_view, name='doctor_list'),
    path('doctors/<int:doctor_id>/', views.doctor_slots_view, name='doctor_slots'),
    path('book/<int:doctor_id>/', views.book_appointment_view, name='book_appointment'),
]