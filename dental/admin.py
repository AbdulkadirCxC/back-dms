from django.contrib import admin
from .models import Patient, Dentist, Appointment, Treatment, PatientTreatment, Invoice, Payment


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'gender', 'date_of_birth', 'phone', 'created_at']
    search_fields = ['full_name', 'phone']


@admin.register(Dentist)
class DentistAdmin(admin.ModelAdmin):
    list_display = ['name', 'specialization']
    search_fields = ['name', 'specialization']


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ['patient', 'dentist', 'appointment_date', 'status']
    list_filter = ['status', 'dentist']
    date_hierarchy = 'appointment_date'


@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ['name', 'cost', 'description']
    search_fields = ['name']


@admin.register(PatientTreatment)
class PatientTreatmentAdmin(admin.ModelAdmin):
    list_display = ['patient', 'treatment', 'dentist', 'date', 'cost_override']
    list_filter = ['dentist', 'date']


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ['patient', 'total_amount', 'status', 'created_at']
    list_filter = ['status']


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'amount', 'method', 'payment_date']
    list_filter = ['method']
