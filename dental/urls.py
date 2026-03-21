from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    PatientViewSet,
    DentistViewSet,
    AppointmentViewSet,
    TreatmentViewSet,
    PatientTreatmentViewSet,
    InvoiceViewSet,
    PaymentViewSet,
)
from .views_reports import (
    dashboard,
    daily_revenue_report,
    patient_treatment_history,
    appointment_report,
    outstanding_payments_report,
    dentist_performance_report,
    most_common_treatments_report,
    payment_method_report,
)

router = DefaultRouter()
router.register(r'patients', PatientViewSet, basename='patient')
router.register(r'dentists', DentistViewSet, basename='dentist')
router.register(r'appointments', AppointmentViewSet, basename='appointment')
router.register(r'treatments', TreatmentViewSet, basename='treatment')
router.register(r'patient-treatments', PatientTreatmentViewSet, basename='patient-treatment')
router.register(r'invoices', InvoiceViewSet, basename='invoice')
router.register(r'payments', PaymentViewSet, basename='payment')

urlpatterns = [
    path('dashboard/', dashboard),
    path('reports/daily-revenue/', daily_revenue_report),
    path('reports/patient-treatment-history/', patient_treatment_history),
    path('reports/appointments/', appointment_report),
    path('reports/outstanding-payments/', outstanding_payments_report),
    path('reports/dentist-performance/', dentist_performance_report),
    path('reports/most-common-treatments/', most_common_treatments_report),
    path('reports/payment-methods/', payment_method_report),
    path('', include(router.urls)),
]
