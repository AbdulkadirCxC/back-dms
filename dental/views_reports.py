"""
Report APIs based on dental_reports_sample.pdf
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import PatientTreatment, Appointment, Invoice, Payment, Dentist, Patient


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    """
    Dashboard API: summary cards and recent appointments.
    Returns: patients, appointments, invoices, users, daily_revenue, monthly_revenue, recent_appointments
    """
    User = get_user_model()
    patients_count = Patient.objects.count()
    appointments_count = Appointment.objects.count()
    invoices_count = Invoice.objects.count()
    users_count = User.objects.count()

    today = timezone.now().date()
    month_start = today.replace(day=1)
    daily_revenue = Payment.objects.filter(payment_date=today).aggregate(total=Sum('amount'))['total'] or Decimal('0')
    monthly_revenue = Payment.objects.filter(
        payment_date__gte=month_start,
        payment_date__lte=today,
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0')

    recent = Appointment.objects.select_related('patient', 'dentist').order_by('-appointment_date')[:10]
    recent_appointments = [
        {
            'id': a.id,
            'date': a.appointment_date.date().isoformat(),
            'time': a.appointment_date.strftime('%H:%M'),
            'patient_name': a.patient.full_name,
            'dentist_name': a.dentist.name,
            'status': a.get_status_display(),
        }
        for a in recent
    ]
    return Response({
        'patients': patients_count,
        'appointments': appointments_count,
        'invoices': invoices_count,
        'users': users_count,
        'daily_revenue': round(float(daily_revenue), 2),
        'monthly_revenue': round(float(monthly_revenue), 2),
        'recent_appointments': recent_appointments,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def daily_revenue_report(request):
    """
    Daily Revenue Report: date, total_patients, total_treatments, total_revenue
    Query params: start_date, end_date (YYYY-MM-DD)
    """
    end = timezone.now().date()
    start = end - timedelta(days=30)
    if 'start_date' in request.query_params:
        start = datetime.strptime(request.query_params['start_date'], '%Y-%m-%d').date()
    if 'end_date' in request.query_params:
        end = datetime.strptime(request.query_params['end_date'], '%Y-%m-%d').date()

    result = []
    current = start
    while current <= end:
        day_pts = PatientTreatment.objects.filter(date=current)
        day_payments = Payment.objects.filter(payment_date=current)
        total_rev = day_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_patients = day_pts.values('patient').distinct().count()
        total_treatments = day_pts.count()
        if total_patients > 0 or total_treatments > 0 or total_rev > 0:
            result.append({
                'date': current.isoformat(),
                'total_patients': total_patients,
                'total_treatments': total_treatments,
                'total_revenue': round(float(total_rev), 2),
            })
        current += timedelta(days=1)
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def patient_treatment_history(request):
    """
    Patient Treatment History: patient_name, treatment, dentist, date, cost
    Query params: patient (id), start_date, end_date
    """
    qs = PatientTreatment.objects.select_related('patient', 'treatment', 'dentist').all()
    if 'patient' in request.query_params:
        qs = qs.filter(patient_id=request.query_params['patient'])
    if 'start_date' in request.query_params:
        qs = qs.filter(date__gte=request.query_params['start_date'])
    if 'end_date' in request.query_params:
        qs = qs.filter(date__lte=request.query_params['end_date'])

    result = [
        {
            'patient_name': pt.patient.full_name,
            'treatment': pt.treatment.name,
            'dentist': pt.dentist.name,
            'date': pt.date.isoformat(),
            'cost': float(pt.effective_cost),
        }
        for pt in qs.order_by('-date')
    ]
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def appointment_report(request):
    """
    Appointment Report: date, patient_name, dentist, time, status
    Query params: start_date, end_date, dentist, status
    """
    qs = Appointment.objects.select_related('patient', 'dentist').all()
    if 'start_date' in request.query_params:
        qs = qs.filter(appointment_date__date__gte=request.query_params['start_date'])
    if 'end_date' in request.query_params:
        qs = qs.filter(appointment_date__date__lte=request.query_params['end_date'])
    if 'dentist' in request.query_params:
        qs = qs.filter(dentist_id=request.query_params['dentist'])
    if 'status' in request.query_params:
        qs = qs.filter(status=request.query_params['status'])

    result = [
        {
            'date': a.appointment_date.date().isoformat(),
            'patient_name': a.patient.full_name,
            'dentist': a.dentist.name,
            'time': a.appointment_date.strftime('%H:%M'),
            'status': a.get_status_display(),
        }
        for a in qs.order_by('-appointment_date', '-id')
    ]
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def outstanding_payments_report(request):
    """
    Outstanding Payments Report: patient_name, invoice_id, total_amount, paid, balance
    Shows invoices that are not fully paid (status pending, unpaid, or partial)
    """
    qs = Invoice.objects.filter(status__in=['pending', 'unpaid', 'partial']).select_related('patient')
    result = []
    for inv in qs:
        paid = inv.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        balance = inv.total_amount - paid
        result.append({
            'patient_name': inv.patient.full_name,
            'invoice_id': inv.id,
            'total_amount': float(inv.total_amount),
            'paid': float(paid),
            'balance': float(balance),
        })
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dentist_performance_report(request):
    """
    Dentist Performance Report: dentist, total_patients, total_treatments, total_revenue
    """
    result = []
    for d in Dentist.objects.all():
        pts = PatientTreatment.objects.filter(dentist=d)
        total_revenue = sum(float(pt.effective_cost) for pt in pts)
        result.append({
            'dentist': d.name,
            'total_patients': pts.values('patient').distinct().count(),
            'total_treatments': pts.count(),
            'total_revenue': round(total_revenue, 2),
        })
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def most_common_treatments_report(request):
    """
    Most Common Treatments: treatment, times_performed, total_revenue
    """
    by_treatment = {}
    for pt in PatientTreatment.objects.select_related('treatment'):
        name = pt.treatment.name
        if name not in by_treatment:
            by_treatment[name] = {'times_performed': 0, 'total_revenue': 0}
        by_treatment[name]['times_performed'] += 1
        by_treatment[name]['total_revenue'] += float(pt.effective_cost)

    result = [
        {'treatment': k, 'times_performed': v['times_performed'], 'total_revenue': round(v['total_revenue'], 2)}
        for k, v in sorted(by_treatment.items(), key=lambda x: -x[1]['times_performed'])
    ]
    return Response(result)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payment_method_report(request):
    """
    Payment Method Report: method, transactions, total_amount
    """
    qs = (
        Payment.objects
        .values('method')
        .annotate(
            transactions=Count('id'),
            total_amount=Sum('amount'),
        )
        .order_by('-transactions')
    )
    method_display = dict(Payment.METHOD_CHOICES)
    result = []
    for row in qs:
        method = method_display.get(row['method'], row['method'])
        result.append({
            'method': method,
            'transactions': row['transactions'],
            'total_amount': float(row['total_amount'] or 0),
        })
    # Include all methods with 0 if not present
    for choice_val, choice_label in Payment.METHOD_CHOICES:
        if not any(r['method'] == choice_label for r in result):
            result.append({'method': choice_label, 'transactions': 0, 'total_amount': 0})
    result.sort(key=lambda x: -x['transactions'])
    return Response(result)
