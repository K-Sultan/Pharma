from django.urls import path
from . import views

urlpatterns = [
    path('', views.consultation_list_view, name='consultation_list'),
]