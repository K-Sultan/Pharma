from django.urls import path
from . import views

urlpatterns = [
    path('', views.ConsultationRecordListCreateView.as_view(), name='consultation-list-create'),
    path('<int:pk>/', views.ConsultationRecordDetailView.as_view(), name='consultation-detail'),
    path('fill/<int:appointment_id>/', views.fill_consultation_view, name='fill_consultation'),
]