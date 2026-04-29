from rest_framework import serializers
from appointments.models import Appointment
from .models import ConsultationRecord, PrescriptionItem

class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = ['id', 'drug', 'dose', 'duration']

class ConsultationRecordSerializer(serializers.ModelSerializer):
    appointment = serializers.PrimaryKeyRelatedField(queryset=Appointment.objects.all())
    prescriptions = PrescriptionItemSerializer(many=True, required=False)

    class Meta:
        model = ConsultationRecord
        fields = [
            'id', 
            'appointment',
            'check_in_time',
            'notes', 
            'diagnosis', 
            'requested_tests', 
            'prescriptions', 
            'created_at', 
            'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']
    
    def create(self, validated_data):
        prescriptions_data = validated_data.pop('prescriptions', [])
        consultation = ConsultationRecord.objects.create(**validated_data)

        for p_data in prescriptions_data:
            PrescriptionItem.objects.create(consultation=consultation, **p_data)

        return consultation

    def update(self, instance, validated_data):
        prescriptions_data = validated_data.pop('prescriptions', None)
        instance.appointment = validated_data.get('appointment', instance.appointment)
        instance.check_in_time = validated_data.get('check_in_time', instance.check_in_time)
        instance.notes = validated_data.get('notes', instance.notes)
        instance.diagnosis = validated_data.get('diagnosis', instance.diagnosis)
        instance.requested_tests = validated_data.get('requested_tests', instance.requested_tests)
        instance.save()

        if prescriptions_data is not None:
            instance.prescriptions.all().delete()
            for p_data in prescriptions_data:
                PrescriptionItem.objects.create(consultation=instance, **p_data)

        return instance
