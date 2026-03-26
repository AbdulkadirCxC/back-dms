from django.db.models import Sum
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Patient, Dentist, Appointment, Treatment, PatientTreatment, Invoice, Payment, PatientRecall, RecallNotification
from .serializers import (
    PatientSerializer,
    DentistSerializer,
    AppointmentSerializer,
    AppointmentStatusUpdateSerializer,
    TreatmentSerializer,
    PatientTreatmentSerializer,
    PatientTreatmentBatchSerializer,
    InvoiceSerializer,
    PaymentSerializer,
    PatientRecallSerializer,
    RecallNotificationSerializer,
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

    @action(detail=True, methods=['post', 'put', 'patch'], url_path='status')
    def update_status(self, request, pk=None):
        """Set appointment status to completed, cancelled, or missed."""
        appointment = self.get_object()
        serializer = AppointmentStatusUpdateSerializer(
            appointment,
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(AppointmentSerializer(appointment).data)


class TreatmentViewSet(viewsets.ModelViewSet):
    queryset = Treatment.objects.all()
    serializer_class = TreatmentSerializer
    search_fields = ['name', 'description']


class PatientTreatmentViewSet(viewsets.ModelViewSet):
    queryset = PatientTreatment.objects.select_related('patient', 'treatment', 'dentist').all()
    serializer_class = PatientTreatmentSerializer
    filterset_fields = ['patient', 'treatment', 'dentist']

    @action(detail=False, methods=['post'], url_path='batch')
    def batch(self, request):
        """
        Add multiple treatments for one patient/dentist/date (Add patient treatments form).
        Payload: { patient, dentist, date, treatments: [{ treatment, cost_override? }, ...] }
        Returns created records + visit_document_url to print one combined invoice.
        """
        serializer = PatientTreatmentBatchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        created = serializer.save()
        data = PatientTreatmentSerializer(created, many=True).data
        ids = [str(pt['id']) for pt in data]
        base_url = request.build_absolute_uri(
            '/api/patient-treatments/visit-document'
        ).rstrip('/')
        visit_document_url = f"{base_url}?ids={','.join(ids)}"
        return Response(
            {
                'patient_treatments': data,
                'visit_document_url': visit_document_url,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=['get'], url_path='visit-document')
    def visit_document(self, request):
        """
        Invoice data for multiple patient treatments (one visit).
        Frontend uses this to render/generate PDF.
        GET ?ids=1,2,3 (comma-separated patient_treatment IDs, same patient).
        """
        ids_param = request.query_params.get('ids', '')
        if not ids_param:
            return Response(
                {'error': 'ids query param required (e.g. ?ids=1,2,3)'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            ids = [int(x.strip()) for x in ids_param.split(',') if x.strip()]
        except ValueError:
            return Response(
                {'error': 'ids must be comma-separated integers'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not ids:
            return Response(
                {'error': 'At least one id required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        qs = PatientTreatment.objects.filter(id__in=ids).select_related(
            'patient', 'treatment', 'dentist'
        )
        pts = list(qs)
        if len(pts) != len(ids):
            return Response(
                {'error': 'Some patient treatment IDs not found'},
                status=status.HTTP_404_NOT_FOUND,
            )
        patients = {p.patient_id for p in pts}
        if len(patients) > 1:
            return Response(
                {'error': 'All treatments must be for the same patient'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        patient = pts[0].patient
        line_items = []
        total = 0
        for pt in pts:
            cost = float(pt.effective_cost)
            line_items.append({
                'name': pt.treatment.name,
                'price': cost,
                'qty': 1,
                'total': cost,
            })
            total += cost
        data = {
            'patient_name': patient.full_name,
            'tel': patient.phone or None,
            'date': pts[0].date.strftime('%Y-%m-%d') if pts else None,
            'doctor': pts[0].dentist.name if pts and pts[0].dentist_id else None,
            'line_items': line_items,
            'grand_total': total,
        }
        return Response(data)


class InvoiceViewSet(viewsets.ModelViewSet):
    queryset = Invoice.objects.select_related('patient').prefetch_related('payments').all()
    serializer_class = InvoiceSerializer
    filterset_fields = ['patient', 'status']

    @action(detail=True, methods=['get'], url_path='voucher')
    def voucher(self, request, pk=None):
        """Return invoice voucher: patient name, tel, treatment, amount, date, doctor."""
        invoice = self.get_object()
        pt = getattr(invoice, 'patient_treatment', None)
        data = {
            'patient_name': invoice.patient.full_name,
            'tel': invoice.patient.phone,
            'treatment': pt.treatment.name if pt and pt.treatment_id else None,
            'amount': float(invoice.total_amount),
            'date': invoice.created_at.strftime('%Y-%m-%d') if invoice.created_at else None,
            'doctor': pt.dentist.name if pt and pt.dentist_id else None,
        }
        return Response(data)


class PatientRecallViewSet(viewsets.ModelViewSet):
    """Patient Recall / Follow-Up API."""
    queryset = PatientRecall.objects.select_related('patient', 'treatment', 'dentist').all()
    serializer_class = PatientRecallSerializer
    filterset_fields = ['patient', 'dentist', 'treatment', 'recall_type', 'status']


class RecallNotificationViewSet(viewsets.ModelViewSet):
    """
    Recall Notifications API.
    Simple workflow: GET due-today -> Staff clicks WhatsApp link -> Sends manually -> PATCH mark-sent
    """
    queryset = RecallNotification.objects.select_related('recall', 'patient', 'recall__dentist').all()
    serializer_class = RecallNotificationSerializer
    filterset_fields = ['recall', 'patient', 'method', 'sent']

    @action(detail=False, methods=['post'], url_path='generate')
    def generate(self, request):
        """
        Create RecallNotifications from active PatientRecalls (reminder 2 days before next_visit).
        POST /api/recall-notifications/generate/
        Call once to backfill existing recalls.
        """
        from datetime import timedelta
        created = 0
        for recall in PatientRecall.objects.filter(status='active', next_visit__isnull=False).select_related('patient'):
            reminder_date = recall.next_visit - timedelta(days=2)
            _, is_new = RecallNotification.objects.get_or_create(
                recall=recall,
                patient=recall.patient,
                reminder_date=reminder_date,
                defaults={'method': 'whatsapp', 'sent': False},
            )
            if is_new:
                created += 1
        return Response({'detail': f'Created {created} notifications'})

    @action(detail=False, methods=['get'], url_path='due-today')
    def due_today(self, request):
        """
        Due reminders: reminder_date <= today and not sent (or exact date if ?date= given).
        GET /api/recall-notifications/due-today/
        GET /api/recall-notifications/due-today/?date=2026-04-08
        """
        from datetime import datetime
        from django.utils import timezone
        from .services.notification_sender import build_recall_message, get_whatsapp_link, get_sms_link

        date_param = request.query_params.get('date')
        if date_param:
            try:
                target_date = datetime.strptime(date_param, '%Y-%m-%d').date()
                qs = RecallNotification.objects.filter(reminder_date=target_date)
            except ValueError:
                target_date = timezone.now().date()
                qs = RecallNotification.objects.filter(reminder_date__lte=target_date, sent=False)
        else:
            target_date = timezone.now().date()
            qs = RecallNotification.objects.filter(reminder_date__lte=target_date, sent=False)

        qs = qs.select_related('recall', 'patient', 'recall__dentist').order_by('reminder_date', 'recall__next_visit')

        result = []
        for n in qs:
            recall = n.recall
            visit_date = recall.next_visit or recall.start_date
            msg = build_recall_message(n)
            result.append({
                'id': n.id,
                'patient': n.patient.full_name,
                'patient_id': n.patient_id,
                'visit_date': visit_date.isoformat() if visit_date else None,
                'reminder_date': n.reminder_date.isoformat(),
                'method': n.method,
                'sent': n.sent,
                'message': msg,
                'whatsapp_link': get_whatsapp_link(n) if n.patient.phone else None,
                'sms_link': get_sms_link(n) if n.patient.phone else None,
            })
        return Response(result)

    @action(detail=True, methods=['post', 'patch'], url_path='mark-sent')
    def mark_sent(self, request, pk=None):
        """
        Mark as sent after staff manually sends via WhatsApp/SMS.
        POST /api/recall-notifications/{id}/mark-sent/
        """
        notification = self.get_object()
        notification.sent = True
        notification.save()
        return Response({'detail': 'Marked as sent', 'sent': True})

    @action(detail=True, methods=['post'], url_path='send')
    def send_notification(self, request, pk=None):
        """
        Send via Twilio API (optional). For simple workflow, use mark-sent instead.
        POST /api/recall-notifications/{id}/send/
        """
        notification = self.get_object()
        if notification.sent:
            return Response(
                {'detail': 'Notification already sent', 'sent': True},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from .services.notification_sender import send_recall_notification
        success, error = send_recall_notification(notification)
        if success:
            notification.sent = True
            notification.save()
            return Response({
                'detail': 'Message sent successfully',
                'sent': True,
                'method': notification.method,
            })
        return Response(
            {'detail': error or 'Failed to send', 'sent': False},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


class PaymentViewSet(viewsets.ModelViewSet):
    queryset = Payment.objects.select_related(
        'invoice',
        'invoice__patient',
        'invoice__patient_treatment__treatment',
        'invoice__patient_treatment__dentist',
    ).all()
    serializer_class = PaymentSerializer
    filterset_fields = ['invoice', 'method']

    @action(detail=True, methods=['get'], url_path='voucher')
    def voucher(self, request, pk=None):
        """Payment voucher data: patient, invoice, amount, method, date, etc."""
        payment = self.get_object()
        invoice = payment.invoice
        patient = invoice.patient
        pt = getattr(invoice, 'patient_treatment', None)
        total_paid = invoice.payments.aggregate(s=Sum('amount'))['s'] or 0
        total_paid = float(total_paid)
        data = {
            'patient_name': patient.full_name,
            'tel': patient.phone or None,
            'invoice_id': invoice.id,
            'invoice_total': float(invoice.total_amount),
            'amount': float(payment.amount),
            'method': payment.method,
            'payment_date': payment.payment_date.strftime('%Y-%m-%d'),
            'treatment': pt.treatment.name if pt and pt.treatment_id else None,
            'doctor': pt.dentist.name if pt and pt.dentist_id else None,
            'total_paid': total_paid,
            'balance': float(invoice.total_amount) - total_paid,
        }
        return Response(data)
