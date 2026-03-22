from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Sum
from django.utils import timezone
from rest_framework import serializers
from .models import Patient, Dentist, Appointment, Treatment, PatientTreatment, Invoice, Payment


class UserRegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('username', 'email', 'password', 'password_confirm')

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('A user with this username already exists.')
        return value

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        return User.objects.create_user(
            username=validated_data['username'],
            email=validated_data.get('email') or '',
            password=validated_data['password'],
        )


class PatientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Patient
        fields = '__all__'
        read_only_fields = ['created_at']

    def validate_gender(self, value):
        """Accept case-insensitive: male, Male, MALE → male; female, Female → female"""
        if value:
            normalized = value.lower()
            if normalized not in ('male', 'female'):
                raise serializers.ValidationError('Must be "male" or "female"')
            return normalized
        return value


class DentistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Dentist
        fields = '__all__'


class AppointmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    dentist_name = serializers.CharField(source='dentist.name', read_only=True)
    date = serializers.DateField(write_only=True, required=False)
    time = serializers.TimeField(write_only=True, required=False)
    appointment_date = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            'id', 'patient', 'patient_name', 'dentist', 'dentist_name',
            'date', 'time', 'appointment_date', 'status', 'notes',
        ]

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if instance.appointment_date:
            data['date'] = instance.appointment_date.strftime('%Y-%m-%d')
            data['time'] = instance.appointment_date.strftime('%H:%M')
        return data

    def validate_status(self, value):
        """Accept case-insensitive status."""
        if value:
            normalized = value.lower()
            valid = (
                'scheduled', 'confirmed', 'completed', 'cancelled',
                'missed', 'no_show',
            )
            if normalized not in valid:
                raise serializers.ValidationError(f'Must be one of: {valid}')
            return normalized
        return value

    def validate(self, attrs):
        date_val = attrs.pop('date', None)
        time_val = attrs.pop('time', None)
        if date_val is not None or time_val is not None:
            if date_val is None:
                date_val = self.instance.appointment_date.date() if self.instance else timezone.now().date()
            if time_val is None:
                time_val = self.instance.appointment_date.time() if self.instance else timezone.now().time()
            from datetime import datetime
            attrs['appointment_date'] = timezone.make_aware(
                datetime.combine(date_val, time_val), timezone.get_current_timezone()
            )
        elif not self.instance:
            raise serializers.ValidationError({'date': 'Date and time are required when creating.'})
        return attrs


_STATUS_ALIASES = {
    'complated': 'completed',
    'cancaled': 'cancelled',
    'canceled': 'cancelled',
}


class AppointmentStatusUpdateSerializer(serializers.ModelSerializer):
    """PATCH /appointments/{id}/status/ — only completed, cancelled, or missed."""

    class Meta:
        model = Appointment
        fields = ('status',)

    def validate_status(self, value):
        if value is None or (isinstance(value, str) and not value.strip()):
            raise serializers.ValidationError('status is required.')
        raw = str(value).strip().lower().replace(' ', '_')
        raw = _STATUS_ALIASES.get(raw, raw)
        allowed = {'completed', 'cancelled', 'missed'}
        if raw not in allowed:
            raise serializers.ValidationError(
                'Status must be one of: completed, cancelled, missed.'
            )
        return raw


class TreatmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Treatment
        fields = '__all__'


class PatientTreatmentSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    treatment_name = serializers.CharField(source='treatment.name', read_only=True)
    dentist_name = serializers.CharField(source='dentist.name', read_only=True)
    effective_cost = serializers.SerializerMethodField()
    invoice_id = serializers.SerializerMethodField()

    class Meta:
        model = PatientTreatment
        fields = [
            'id', 'patient', 'patient_name', 'treatment', 'treatment_name',
            'dentist', 'dentist_name', 'date', 'cost_override', 'effective_cost',
            'invoice_id',
        ]

    def get_effective_cost(self, obj):
        return float(obj.effective_cost)

    def get_invoice_id(self, obj):
        try:
            return obj.invoice.id
        except ObjectDoesNotExist:
            return None


class TreatmentItemSerializer(serializers.Serializer):
    """Single treatment row: treatment (+ treatment_id alias) + optional cost_override."""

    treatment = serializers.PrimaryKeyRelatedField(queryset=Treatment.objects.all())
    cost_override = serializers.DecimalField(
        max_digits=10, decimal_places=2, required=False, allow_null=True
    )

    def to_internal_value(self, data):
        data = dict(data)
        if 'treatment_id' in data and 'treatment' not in data:
            data['treatment'] = data['treatment_id']
            del data['treatment_id']
        return super().to_internal_value(data)


class PatientTreatmentBatchSerializer(serializers.Serializer):
    """Bulk add: patient, dentist, date + list of treatments (Add patient treatments form)."""

    patient = serializers.PrimaryKeyRelatedField(queryset=Patient.objects.all())
    dentist = serializers.PrimaryKeyRelatedField(queryset=Dentist.objects.all())
    date = serializers.DateField(
        input_formats=['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y'],
    )
    treatments = serializers.ListField(
        child=TreatmentItemSerializer(),
        min_length=1,
    )

    def to_internal_value(self, data):
        data = dict(data)
        if 'patient_id' in data and 'patient' not in data:
            data['patient'] = data['patient_id']
            del data['patient_id']
        if 'dentist_id' in data and 'dentist' not in data:
            data['dentist'] = data['dentist_id']
            del data['dentist_id']
        return super().to_internal_value(data)

    def create(self, validated_data):
        treatments_data = validated_data.pop('treatments')
        created = []
        for item in treatments_data:
            pt = PatientTreatment.objects.create(
                patient=validated_data['patient'],
                dentist=validated_data['dentist'],
                date=validated_data['date'],
                treatment=item['treatment'],
                cost_override=item.get('cost_override'),
            )
            created.append(pt)
        return created


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = '__all__'

    def validate_method(self, value):
        """Accept case-insensitive method: cash, Cash → cash; evc plus → evc_plus."""
        if value:
            normalized = value.lower().replace(' ', '_').replace('evcplus', 'evc_plus')
            valid = ('evc_plus', 'cash', 'card', 'mobile', 'bank_transfer', 'other')
            if normalized in valid:
                return normalized
            # Map common variants
            if normalized in ('evcplus',):
                return 'evc_plus'
            if normalized in ('banktransfer',):
                return 'bank_transfer'
            raise serializers.ValidationError(f'Must be one of: {valid}')
        return value


class InvoiceSerializer(serializers.ModelSerializer):
    patient_name = serializers.CharField(source='patient.full_name', read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)
    paid_amount = serializers.SerializerMethodField()
    balance = serializers.SerializerMethodField()

    class Meta:
        model = Invoice
        fields = '__all__'

    def get_paid_amount(self, obj):
        total = obj.payments.aggregate(s=Sum('amount'))['s']
        return float(total) if total is not None else 0.0

    def get_balance(self, obj):
        total_amount = float(obj.total_amount)
        paid = self.get_paid_amount(obj)
        return round(total_amount - paid, 2)

    def validate_status(self, value):
        """Accept case-insensitive status."""
        if value:
            normalized = value.lower()
            valid = ('pending', 'paid', 'unpaid', 'partial')
            if normalized not in valid:
                raise serializers.ValidationError(f'Must be one of: {valid}')
            return normalized
        return value
