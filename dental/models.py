"""
Dental Management System models - based on PDF schema.
"""
from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    """Activity/audit log for API actions."""
    ACTION_CHOICES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs',
    )
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='other')
    path = models.CharField(max_length=500)
    method = models.CharField(max_length=10)
    resource = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    extra = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.action} {self.resource or self.path} by {self.user} at {self.created_at}'


class UserProfile(models.Model):
    """Extended user profile with avatar."""
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    avatar = models.ImageField(upload_to='avatars/', blank=True, null=True)

    def __str__(self):
        return f'Profile of {self.user.username}'


class Patient(models.Model):
    full_name = models.CharField(max_length=255)
    GENDER_CHOICES = [
        ('male', 'Male'),
        ('female', 'Female'),
    ]
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    date_of_birth = models.DateField()
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['full_name']

    def __str__(self):
        return self.full_name


class Dentist(models.Model):
    name = models.CharField(max_length=255)
    specialization = models.CharField(max_length=100)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Appointment(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('confirmed', 'Confirmed'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('missed', 'Missed'),
        ('no_show', 'No Show'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    dentist = models.ForeignKey(Dentist, on_delete=models.CASCADE, related_name='appointments')
    appointment_date = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-appointment_date']

    def __str__(self):
        return f"{self.patient} - {self.dentist} ({self.appointment_date})"


class Treatment(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class PatientTreatment(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='patient_treatments')
    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE, related_name='patient_treatments')
    dentist = models.ForeignKey(Dentist, on_delete=models.CASCADE, related_name='patient_treatments')
    date = models.DateField()
    cost_override = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True,
        help_text='Override treatment cost for this patient if set'
    )

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.patient} - {self.treatment} ({self.date})"

    @property
    def effective_cost(self):
        return self.cost_override if self.cost_override is not None else self.treatment.cost


class Invoice(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='invoices')
    patient_treatment = models.OneToOneField(
        PatientTreatment, on_delete=models.CASCADE, null=True, blank=True,
        related_name='invoice'
    )
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Invoice #{self.pk} - {self.patient} ({self.total_amount})"


class Payment(models.Model):
    METHOD_CHOICES = [
        ('evc_plus', 'EVC Plus'),
        ('cash', 'Cash'),
        ('card', 'Card'),
        ('mobile', 'Mobile'),
        ('bank_transfer', 'Bank Transfer'),
        ('other', 'Other'),
    ]

    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=50, choices=METHOD_CHOICES)
    payment_date = models.DateField()

    class Meta:
        ordering = ['-payment_date']

    def __str__(self):
        return f"{self.amount} - {self.method} ({self.payment_date})"


class PatientRecall(models.Model):
    """
    Patient Recall / Follow-Up: schedule when patients must return.
    Table: patient_recalls
    """
    RECALL_TYPE_CHOICES = [
        ('monthly', 'Monthly'),
        ('cleaning', 'Cleaning'),
        ('checkup', 'Checkup'),
    ]
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    ]

    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name='recalls',
        help_text='Which patient must return',
    )
    treatment = models.ForeignKey(
        Treatment, on_delete=models.CASCADE, related_name='recalls',
        null=True, blank=True,
        help_text='Treatment related to the recall',
    )
    dentist = models.ForeignKey(
        Dentist, on_delete=models.CASCADE, related_name='recalls',
        help_text='Responsible dentist',
    )
    recall_type = models.CharField(
        max_length=20, choices=RECALL_TYPE_CHOICES,
        help_text='Type of follow-up',
    )
    day_of_month = models.PositiveSmallIntegerField(
        default=1,
        help_text='Specific day patient must come (1-31)',
    )
    interval_months = models.PositiveIntegerField(
        default=6,
        help_text='How often patient returns (in months)',
    )
    start_date = models.DateField(
        help_text='First visit date',
    )
    next_visit = models.DateField(
        null=True, blank=True,
        help_text='Automatically calculated next visit',
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default='active',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-next_visit', '-created_at']
        verbose_name = 'Patient Recall'
        verbose_name_plural = 'Patient Recalls'

    def __str__(self):
        return f'{self.patient} - {self.recall_type} ({self.next_visit or self.start_date})'

    def calculate_next_visit(self, from_date=None):
        """Calculate next visit date from start_date + interval_months, using day_of_month."""
        from datetime import date
        from calendar import monthrange
        base = from_date or self.start_date
        if isinstance(base, str):
            from datetime import datetime
            base = datetime.strptime(base, '%Y-%m-%d').date()
        year, month = base.year, base.month
        month += self.interval_months
        while month > 12:
            month -= 12
            year += 1
        day = min(self.day_of_month, monthrange(year, month)[1])
        return date(year, month, day)

    def save(self, *args, **kwargs):
        if self.next_visit is None and self.start_date and self.status == 'active':
            try:
                self.next_visit = self.calculate_next_visit()
            except Exception:
                pass
        super().save(*args, **kwargs)


class RecallNotification(models.Model):
    """
    Recall Notifications: track reminder messages sent for patient recalls.
    Table: recall_notifications
    """
    METHOD_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('sms', 'SMS'),
    ]

    recall = models.ForeignKey(
        PatientRecall, on_delete=models.CASCADE, related_name='notifications',
        help_text='Related recall',
    )
    patient = models.ForeignKey(
        Patient, on_delete=models.CASCADE, related_name='recall_notifications',
        help_text='Patient to notify',
    )
    reminder_date = models.DateField(
        help_text='Date the reminder is scheduled for',
    )
    method = models.CharField(
        max_length=20, choices=METHOD_CHOICES,
    )
    sent = models.BooleanField(
        default=False,
        help_text='Whether the notification was sent',
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-reminder_date', '-created_at']
        verbose_name = 'Recall Notification'
        verbose_name_plural = 'Recall Notifications'

    def __str__(self):
        return f'{self.patient} - {self.method} ({self.reminder_date}) - {"Sent" if self.sent else "Pending"}'
