from django.contrib import admin
from .models import Patient, Dentist, Appointment, Treatment, PatientTreatment, Invoice, Payment, AuditLog, PatientRecall, RecallNotification


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action', 'method', 'resource', 'path']
    list_filter = ['action', 'method', 'resource']
    search_fields = ['path', 'resource', 'object_repr']
    readonly_fields = ['user', 'action', 'path', 'method', 'resource', 'object_id', 'object_repr', 'ip_address', 'user_agent', 'extra', 'created_at']


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


@admin.register(PatientRecall)
class PatientRecallAdmin(admin.ModelAdmin):
    list_display = ['patient', 'dentist', 'recall_type', 'start_date', 'next_visit', 'status']
    list_filter = ['recall_type', 'status', 'dentist']
    date_hierarchy = 'next_visit'
    search_fields = ['patient__full_name']


@admin.register(RecallNotification)
class RecallNotificationAdmin(admin.ModelAdmin):
    list_display = ['recall', 'patient', 'reminder_date', 'method', 'sent', 'created_at']
    list_filter = ['method', 'sent']
    date_hierarchy = 'reminder_date'
    search_fields = ['patient__full_name']
