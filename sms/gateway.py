import logging
import requests
from django.conf import settings

logger = logging.getLogger(__name__)


def send_sms(phone: str, message: str) -> bool:
    if not getattr(settings, "SMS_ENABLED", False):
        logger.info(f"[SMS DISABLED] To {phone}: {message}")
        return True

    provider = getattr(settings, "SMS_PROVIDER", "bulksms").lower()

    try:
        if provider == "bulksms":
            return _bulksms(phone, message)
        elif provider == "twilio":
            return _twilio(phone, message)
        elif provider == "africas_talking":
            return _africas_talking(phone, message)
        else:
            logger.error(f"Unknown SMS provider: {provider}")
            return False
    except Exception as e:
        logger.error(f"SMS send failed to {phone}: {e}")
        return False


def _bulksms(phone: str, message: str) -> bool:
    resp = requests.post(
        "https://api.bulksms.com/v1/messages",
        auth=(settings.SMS_API_KEY, settings.SMS_API_SECRET),
        json={
            "to": phone,
            "body": message,
            "from": settings.SMS_SENDER_ID,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return True


def _twilio(phone: str, message: str) -> bool:
    from twilio.rest import Client
    client = Client(settings.SMS_API_KEY, settings.SMS_API_SECRET)
    client.messages.create(body=message, from_=settings.SMS_SENDER_ID, to=phone)
    return True


def _africas_talking(phone: str, message: str) -> bool:
    resp = requests.post(
        "https://api.africastalking.com/version1/messaging",
        headers={
            "apiKey": settings.SMS_API_KEY,
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "username": settings.SMS_API_SECRET,
            "to": phone,
            "message": message,
            "from": settings.SMS_SENDER_ID,
        },
        timeout=10,
    )
    resp.raise_for_status()
    return True
