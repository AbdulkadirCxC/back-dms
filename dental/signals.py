from decimal import Decimal

from django.db.models import Sum
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver

from .models import PatientTreatment, Invoice, Payment


@receiver(post_save, sender=PatientTreatment)
def create_invoice_for_patient_treatment(sender, instance, created, **kwargs):
    """Create an invoice when a PatientTreatment is created."""
    if created:
        Invoice.objects.create(
            patient=instance.patient,
            patient_treatment=instance,
            total_amount=instance.effective_cost,
            status='pending',
        )


def update_invoice_status(invoice):
    """Update invoice status based on total payments."""
    total_paid = invoice.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0')
    if total_paid >= invoice.total_amount:
        invoice.status = 'paid'
    elif total_paid > 0:
        invoice.status = 'partial'
    else:
        invoice.status = 'pending'
    invoice.save(update_fields=['status'])


@receiver(post_save, sender=Payment)
def update_invoice_on_payment_save(sender, instance, created, **kwargs):
    """Update invoice status when a Payment is added or updated."""
    update_invoice_status(instance.invoice)


@receiver(post_delete, sender=Payment)
def update_invoice_on_payment_delete(sender, instance, **kwargs):
    """Update invoice status when a Payment is deleted."""
    update_invoice_status(instance.invoice)
