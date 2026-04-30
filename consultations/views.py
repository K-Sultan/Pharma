from rest_framework import generics, permissions
from .models import ConsultationRecord
from .serializers import ConsultationRecordSerializer

class ConsultationRecordListCreateView(generics.ListCreateAPIView):
    queryset = ConsultationRecord.objects.select_related("appointment").prefetch_related("prescriptions")
    serializer_class = ConsultationRecordSerializer
    permission_classes = [permissions.IsAuthenticated]

class ConsultationRecordDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = ConsultationRecord.objects.select_related("appointment").prefetch_related("prescriptions")
    serializer_class = ConsultationRecordSerializer
    permission_classes = [permissions.IsAuthenticated]
