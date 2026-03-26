"""
Recall notification sender: WhatsApp and SMS.
Simple workflow: Staff clicks link -> WhatsApp/SMS app opens with message -> Staff sends.

Optional: Twilio for API sending (configure in .env)
"""
import logging
from urllib.parse import quote

from django.conf import settings

logger = logging.getLogger(__name__)


def normalize_phone_for_link(phone: str) -> str:
    """Normalize phone to digits only for wa.me (e.g. 252611234567)."""
    if not phone:
        return ''
    digits = ''.join(c for c in str(phone) if c.isdigit())
    if digits.startswith('0'):
        digits = digits[1:]
    return digits


def build_recall_message(notification):
    """Build reminder message for patient."""
    recall = notification.recall
    patient = notification.patient
    dentist = recall.dentist
    next_date = recall.next_visit or recall.start_date
    return (
        f"Hi {patient.full_name}, this is a reminder from your dentist. "
        f"Your next {recall.get_recall_type_display()} appointment with Dr. {dentist.name} "
        f"is scheduled for {next_date}. Please confirm or reschedule."
    )


def get_whatsapp_link(notification) -> str:
    """
    Returns wa.me link - opens WhatsApp with pre-filled message.
    Staff clicks, edits if needed, presses Send.
    """
    phone = normalize_phone_for_link(notification.patient.phone)
    if not phone:
        return ''
    message = build_recall_message(notification)
    text = quote(message)
    return f'https://wa.me/{phone}?text={text}'


def get_sms_link(notification) -> str:
    """
    Returns sms: link - opens default SMS app with pre-filled message (mobile).
    """
    phone = notification.patient.phone or ''
    phone = ''.join(c for c in str(phone) if c.isdigit() or c == '+')
    if not phone or not phone.lstrip('+'):
        return ''
    if not phone.startswith('+'):
        phone = '+' + phone
    message = build_recall_message(notification)
    body = quote(message)
    return f'sms:{phone}?body={body}'


def send_sms(phone: str, message: str) -> tuple[bool, str]:
    """
    Send SMS via Twilio. Returns (success, error_message).
    Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE in .env
    """
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
    from_phone = getattr(settings, 'TWILIO_PHONE', None)

    if not all([sid, token, from_phone]):
        logger.warning('Twilio not configured: set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE')
        return False, 'SMS not configured. Add Twilio credentials to .env'

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        # Normalize phone to E.164
        to = phone.strip()
        if not to.startswith('+'):
            to = '+' + to.lstrip('0')
        client.messages.create(body=message, from_=from_phone, to=to)
        return True, ''
    except Exception as e:
        logger.exception('SMS send failed')
        return False, str(e)


def send_whatsapp(phone: str, message: str) -> tuple[bool, str]:
    """
    Send WhatsApp via Twilio. Returns (success, error_message).
    Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM (e.g. whatsapp:+14155238886)
    """
    sid = getattr(settings, 'TWILIO_ACCOUNT_SID', None)
    token = getattr(settings, 'TWILIO_AUTH_TOKEN', None)
    from_wa = getattr(settings, 'TWILIO_WHATSAPP_FROM', None)

    if not all([sid, token, from_wa]):
        logger.warning('WhatsApp not configured: set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_FROM')
        return False, 'WhatsApp not configured. Add Twilio credentials to .env'

    try:
        from twilio.rest import Client
        client = Client(sid, token)
        to = phone.strip()
        if not to.startswith('+'):
            to = '+' + to.lstrip('0')
        to_wa = f'whatsapp:{to}'
        if not from_wa.startswith('whatsapp:'):
            from_wa = f'whatsapp:{from_wa}'
        client.messages.create(body=message, from_=from_wa, to=to_wa)
        return True, ''
    except Exception as e:
        logger.exception('WhatsApp send failed')
        return False, str(e)


def send_recall_notification(notification) -> tuple[bool, str]:
    """
    Send a recall notification. Returns (success, error_message).
    """
    phone = notification.patient.phone
    if not phone or not phone.strip():
        return False, 'Patient has no phone number'

    message = build_recall_message(notification)

    if notification.method == 'whatsapp':
        return send_whatsapp(phone, message)
    elif notification.method == 'sms':
        return send_sms(phone, message)
    else:
        return False, f'Unknown method: {notification.method}'
