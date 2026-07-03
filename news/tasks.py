import json

from celery import shared_task
from django.conf import settings
from pywebpush import webpush, WebPushException

from .models import Post, PushSubscription, NotificationEvent


@shared_task
def send_push_for_post(post_id):
    """Fan out a push notification to every active subscriber for a
    published post. Each push carries the NotificationEvent's own id in
    its payload — the service worker echoes that id back to the backend
    when it delivers and when it's clicked, which is how per-post
    delivered/clicked stats get built."""
    try:
        post = Post.objects.get(pk=post_id)
    except Post.DoesNotExist:
        return

    for sub in PushSubscription.objects.filter(is_active=True):
        event = NotificationEvent.objects.create(subscription=sub, post=post, status='sent')
        payload = {
            'id': event.id,
            'title': 'DigitalTouch News',
            'body': post.excerpt,
            'url': f'https://news.digitaltouch.co.zw/#{post.slug}',
        }
        try:
            webpush(
                subscription_info={
                    'endpoint': sub.endpoint,
                    'keys': {'p256dh': sub.p256dh, 'auth': sub.auth},
                },
                data=json.dumps(payload),
                vapid_private_key=settings.VAPID_PRIVATE_KEY,
                vapid_claims={'sub': f'mailto:{settings.VAPID_CLAIM_EMAIL}'},
            )
        except WebPushException as ex:
            # 404/410 means the browser subscription is gone for good
            # (uninstalled, cleared storage, etc.) — stop sending to it.
            status_code = getattr(ex.response, 'status_code', None)
            if status_code in (404, 410):
                sub.is_active = False
                sub.save(update_fields=['is_active'])

