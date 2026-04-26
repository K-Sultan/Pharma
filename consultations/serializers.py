from rest_framework import serializers
from .models import ConsultationRecord, PrescriptionItem

class PrescriptionItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = PrescriptionItem
        fields = ['id', 'drug', 'dose', 'duration']

class ConsultationRecordSerializer(serializers.ModelSerializer):
    """
    Serializer for the ConsultationRecord model. 
    Includes nested serialization for PrescriptionItems.
    """
    prescriptions = PrescriptionItemSerializer(many=True, required=False)

    class Meta:
        model = ConsultationRecord
        fields = [
            'id', 
            'notes', 
            'diagnosis', 
            'requested_tests', 
            'prescriptions', 
            'created_at', 
            'updated_at'
        ]
    
    def create(self, validated_data):
        # Extract nested prescriptions data before creating the consultation
        prescriptions_data = validated_data.pop('prescriptions', [])
        
        # Create the consultation record
        consultation = ConsultationRecord.objects.create(**validated_data)
        
        # Create related prescription items
        for p_data in prescriptions_data:
            PrescriptionItem.objects.create(consultation=consultation, **p_data)
            
        return consultation

    def update(self, instance, validated_data):
        # Extract nested prescriptions data
        prescriptions_data = validated_data.pop('prescriptions', None)
        
        # Update ConsultationRecord fields
        instance.notes = validated_data.get('notes', instance.notes)
        instance.diagnosis = validated_data.get('diagnosis', instance.diagnosis)
        instance.requested_tests = validated_data.get('requested_tests', instance.requested_tests)
        instance.save()
        
        # If prescriptions are provided, we overwrite the existing ones
        if prescriptions_data is not None:
            instance.prescriptions.all().delete()
            for p_data in prescriptions_data:
                PrescriptionItem.objects.create(consultation=instance, **p_data)
                
        return instance
