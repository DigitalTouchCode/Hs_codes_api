import logging
from celery import shared_task
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_status_sms(self, repair_id: str, new_status: str, log_id: int = None):
    try:
        from repairs.models import Repair, RepairStatusLog, STATUS_SMS_TEMPLATES
        from sms.gateway import send_sms

        repair = Repair.objects.select_related("client").get(id=repair_id)
        template = STATUS_SMS_TEMPLATES.get(new_status)
        if not template:
            return

        track_url = f"{getattr(settings, 'FRONTEND_URL', '')}/track/{repair.ref}"
        message = template.format(
            name=repair.client.first_name,
            ref=repair.ref,
            track_url=track_url,
        )

        success = send_sms(repair.client.phone, message)

        if log_id and success:
            RepairStatusLog.objects.filter(id=log_id).update(sms_sent=True)

    except Exception as exc:
        logger.error(f"send_status_sms failed for repair {repair_id}: {exc}")
        raise self.retry(exc=exc)
