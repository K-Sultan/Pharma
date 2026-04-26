from django.urls import path
from . import views

urlpatterns = [
    path('', views.appointment_list_view, name='appointment_list'),
]