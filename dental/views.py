from django.utils import timezone
from rest_framework import viewsets
from .models import Patient, Dentist, Appointment, Treatment, PatientTreatment, Invoice, Payment
from .serializers import (
    PatientSerializer,
    DentistSerializer,
    AppointmentSerializer,
    TreatmentSerializer,
    PatientTreatmentSerializer,
    InvoiceSerializer,
    PaymentSerializer,
)


class PatientViewSet(viewsets.ModelViewSet):
    """Patient API: list, retrieve, create, update, delete."""
    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    search_fields = ['full_name', 'phone']


class DentistViewSet(viewsets.ModelViewSet):
    queryset = Dentist.objects.all()
    serializer_class = DentistSerializer
    search_fields = ['name', 'specialization']


class AppointmentViewSet(viewsets.ModelViewSet):
    queryset = Appointment.objects.select_related('patient', 'dentist').all()
    serializer_class = AppointmentSerializer
    filterset_fields = ['patient', 'dentist', 'status']

    def get_serializer(self, *args, **kwargs):
        # Fix DRF Browsable API form: provide valid initial data
        if self.action == 'list' and not args and not kwargs.get('instance') and not kwargs.get('data'):
            patient = Patient.objects.first()
            dentist = Dentist.objects.first()
            now = timezone.now()
            if patient and dentist:
                kwargs['data'] = {
                    'patient': patient.pk,
                    'dentist': dentist.pk,
                    'date': now.strftime('%Y-%m-%d'),
                    'time': now.strftime('%H:%M'),
                    'status': 'confirmed',
                    'notes': '',
                }
            else:
                kwargs['data'] = {
                    'date': now.strftime('%Y-%m-%d'),
                    'time': now.strftime('%H:%M'),
                    'notes': '',
                }
        return super().get_serializer(*args, **kwargs)


class TreatmentViewSet(viewsets.ModelViewSet):
    queryset = Treatment.objects.all()
    serializer_class = TreatmentSerializer
    search_fields = ['name', 'description']


class PatientTreatmentViewSet(viewsets.ModelViewSet):
    queryset = PatientTreatment.objects.select_related('patient', 'treatment', 'dentist').all()
    serializer_class = PatientTreatmentSerializer
    filterset_fields = ['patient', 'treatment', 'dentist']


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related('patient').prefetch_related('payments').all()
    serializer_class = InvoiceSerializer
    filterset_fields = ['patient', 'status']


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related('invoice').all()
    serializer_class = PaymentSerializer
    filterset_fields = ['invoice', 'method']
