import json

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from pywebpush import webpush, WebPushException

from .models import Post, PushSubscription, NotificationEvent, Subscriber


@shared_task
def send_thank_you_email(subscriber_id):
    """Fires once — only when GoogleAuthView creates a brand new
    Subscriber row, never on a repeat sign-in from the same person."""
    try:
        subscriber = Subscriber.objects.get(pk=subscriber_id)
    except Subscriber.DoesNotExist:
        return

    first_name = (subscriber.name or '').split(' ')[0] or 'there'
    subject = 'Thanks for subscribing to DigitalTouch News'

    text_body = (
        f"Hi {first_name},\n\n"
        "Thanks for signing up for DigitalTouch News. You'll hear from us "
        "whenever we publish good Tech News., "
        "\n\n"
        "— The DigitalTouch team\n"
        "https://news.digitaltouch.co.zw"
    )

    html_body = f"""
    <div style="font-family: -apple-system, Helvetica, Arial, sans-serif; max-width: 480px; margin: 0 auto; color: #1d1d1f;">
      <h2 style="font-size: 20px; margin-bottom: 12px;">Thanks for subscribing, {first_name}.</h2>
      <p style="font-size: 15px; line-height: 1.6; color: #333;">
        You're now signed up for DigitalTouch News. We'll only get in touch
        when there's something worth your time — product updates, ZIMRA
        compliance changes, and the occasional deep dive into Zimbabwean tech.
      </p>
      <p style="margin-top: 24px;">
        <a href="https://news.digitaltouch.co.zw"
           style="background:#0073e6; color:#ffffff; text-decoration:none;
                  padding:10px 20px; border-radius:980px; font-size:14px; display:inline-block;">
          Visit DigitalTouch News
        </a>
      </p>
      <p style="font-size: 12px; color: #aeaeb2; margin-top: 32px;">
        DigitalTouch &middot; Harare, Zimbabwe
      </p>
    </div>
    """

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[subscriber.email],
    )
    msg.attach_alternative(html_body, 'text/html')
    msg.send(fail_silently=False)


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

