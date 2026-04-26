from rest_framework import generics
from .models import ConsultationRecord
from .serializers import ConsultationRecordSerializer

# Simple DRF Generic views for creating and listing consultations
class ConsultationRecordListCreateView(generics.ListCreateAPIView):
    """
    GET: List all consultation records.
    POST: Create a new consultation record with optional nested prescriptions.
    """
    queryset = ConsultationRecord.objects.all()
    serializer_class = ConsultationRecordSerializer

# Simple DRF Generic views for retrieving, updating, and deleting consultations
class ConsultationRecordDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    GET: Retrieve a specific consultation record.
    PUT/PATCH: Update a consultation record.
    DELETE: Delete a consultation record.
    """
    queryset = ConsultationRecord.objects.all()
    serializer_class = ConsultationRecordSerializer