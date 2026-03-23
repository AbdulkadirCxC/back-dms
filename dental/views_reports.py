"""
Report APIs based on dental_reports_sample.pdf
"""
from datetime import datetime, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Sum, Count
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response

from .models import PatientTreatment, Appointment, Invoice, Payment, Dentist, Patient, AuditLog


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
def customer_statement(request):
    """
    Customer Statement API: ledger-style transactions with running balance.
    Query params: patient (required), start_date, end_date (YYYY-MM-DD)
    Returns: patient info, transactions (DATE, TYPE, INVOICE, DESCRIPTION, PAYMENT, AMOUNT, BALANCE)
    """
    patient_id = request.query_params.get('patient')
    if not patient_id:
        return Response(
            {'error': 'patient query param required (patient id)'},
            status=400,
        )
    try:
        patient = Patient.objects.get(pk=patient_id)
    except (Patient.DoesNotExist, ValueError):
        return Response(
            {'error': 'Patient not found'},
            status=404,
        )

    start_date = request.query_params.get('start_date')
    end_date = request.query_params.get('end_date')
    if start_date:
        try:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'start_date must be YYYY-MM-DD'},
                status=400,
            )
    if end_date:
        try:
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'end_date must be YYYY-MM-DD'},
                status=400,
            )

    # Opening balance (charges - payments before start_date)
    opening_balance = Decimal('0')
    if start_date:
        before_invoices = Invoice.objects.filter(
            patient=patient
        ).filter(created_at__date__lt=start_date)
        before_payments = Payment.objects.filter(
            invoice__patient=patient
        ).filter(payment_date__lt=start_date)
        total_before_charges = before_invoices.aggregate(s=Sum('total_amount'))['s'] or Decimal('0')
        total_before_payments = before_payments.aggregate(s=Sum('amount'))['s'] or Decimal('0')
        opening_balance = total_before_charges - total_before_payments

    # Build rows: (date, type, invoice_id, description, payment, amount)
    rows = []

    invoices = Invoice.objects.filter(patient=patient).select_related(
        'patient_treatment__treatment', 'patient_treatment__dentist'
    )
    if start_date:
        invoices = invoices.filter(created_at__date__gte=start_date)
    if end_date:
        invoices = invoices.filter(created_at__date__lte=end_date)

    for inv in invoices:
        desc = (
            inv.patient_treatment.treatment.name
            if inv.patient_treatment_id and inv.patient_treatment.treatment_id
            else f'Invoice #{inv.id}'
        )
        date_val = inv.created_at.date() if inv.created_at else None
        rows.append({
            'date': date_val.isoformat() if date_val else None,
            'type': 'charge',
            'invoice': inv.id,
            'description': desc,
            'payment': 0,
            'amount': float(inv.total_amount),
        })

    payments = Payment.objects.filter(invoice__patient=patient).select_related('invoice')
    if start_date:
        payments = payments.filter(payment_date__gte=start_date)
    if end_date:
        payments = payments.filter(payment_date__lte=end_date)

    for p in payments:
        method_display = dict(Payment.METHOD_CHOICES).get(p.method, p.method)
        rows.append({
            'date': p.payment_date.isoformat(),
            'type': 'payment',
            'invoice': p.invoice_id,
            'description': f'Payment Received ({method_display})',
            'payment': float(p.amount),
            'amount': 0,
        })

    rows.sort(key=lambda r: (r['date'] or '0000-00-00', 0 if r['type'] == 'charge' else 1))

    total_charges = sum(r['amount'] for r in rows)
    total_payments = sum(r['payment'] for r in rows)

    def _format_mdy(d):
        """Format date as M/D/YY (e.g. 1/15/12)."""
        if isinstance(d, str):
            try:
                d = datetime.strptime(d, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                return d
        if hasattr(d, 'month'):
            return f'{d.month}/{d.day}/{str(d.year)[2:]}'
        return str(d)

    # Build ledger with running balance: Previous Balance + AMOUNT - PAYMENT
    transactions = []
    balance = float(opening_balance)

    # Balance Forward row
    period_start = start_date
    if not period_start and rows:
        try:
            period_start = datetime.strptime(rows[0]['date'], '%Y-%m-%d').date()
        except (ValueError, TypeError):
            period_start = timezone.now().date()
    if not period_start:
        period_start = timezone.now().date()
    transactions.append({
        'date': _format_mdy(period_start),
        'type': '',
        'invoice': None,
        'description': 'Balance Forward',
        'payment': 0,
        'amount': 0,
        'balance': round(balance, 2),
    })

    for r in rows:
        balance = balance + r['amount'] - r['payment']
        transactions.append({
            'date': _format_mdy(r['date']) if r['date'] else None,
            'type': r['type'].capitalize(),
            'invoice': r['invoice'],
            'description': r['description'],
            'payment': r['payment'] if r['payment'] else 0,
            'amount': r['amount'] if r['amount'] else 0,
            'balance': round(balance, 2),
        })

    return Response({
        'patient': {
            'id': patient.id,
            'full_name': patient.full_name,
            'phone': patient.phone,
            'date_of_birth': patient.date_of_birth.isoformat(),
        },
        'statement_date': timezone.now().date().isoformat(),
        'transactions': transactions,
        'summary': {
            'total_charges': round(total_charges, 2),
            'total_payments': round(total_payments, 2),
            'balance_due': round(balance, 2),
        },
    })


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


@api_view(['GET'])
@permission_classes([IsAdminUser])
def activity_logs(request):
    """
    Activity/Audit logs report.
    Query params: user, action, resource, start_date, end_date, limit
    """
    qs = AuditLog.objects.select_related('user').all()

    if 'user' in request.query_params:
        qs = qs.filter(user_id=request.query_params['user'])
    if 'action' in request.query_params:
        qs = qs.filter(action=request.query_params['action'])
    if 'resource' in request.query_params:
        qs = qs.filter(resource__icontains=request.query_params['resource'])
    if 'start_date' in request.query_params:
        try:
            start = datetime.strptime(request.query_params['start_date'], '%Y-%m-%d')
            qs = qs.filter(created_at__date__gte=start.date())
        except ValueError:
            pass
    if 'end_date' in request.query_params:
        try:
            end = datetime.strptime(request.query_params['end_date'], '%Y-%m-%d')
            qs = qs.filter(created_at__date__lte=end.date())
        except ValueError:
            pass

    limit = 100
    if 'limit' in request.query_params:
        try:
            limit = min(500, max(1, int(request.query_params['limit'])))
        except ValueError:
            pass

    qs = qs.order_by('-created_at')[:limit]

    result = [
        {
            'id': log.id,
            'user': log.user.username if log.user_id else None,
            'user_id': log.user_id,
            'action': log.action,
            'path': log.path,
            'method': log.method,
            'resource': log.resource or None,
            'object_id': log.object_id or None,
            'object_repr': log.object_repr or None,
            'ip_address': str(log.ip_address) if log.ip_address else None,
            'created_at': log.created_at.isoformat() if log.created_at else None,
        }
        for log in qs
    ]
    return Response(result)
