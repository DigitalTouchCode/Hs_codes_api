import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, generics, permissions, pagination, status, parsers
from rest_framework.response import Response
from rest_framework.views import APIView
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_requests

from .auth import issue_admin_token, SignedTokenAuthentication
from .models import Post, PushSubscription, NotificationEvent, Subscriber
from .serializers import (
    PostSerializer, PostWriteSerializer, PushSubscriptionSerializer, NotificationEventSerializer,
    SubscriberSerializer, NewsletterSendSerializer,
)
from .tasks import send_push_for_post, send_thank_you_email, send_newsletter

logger = logging.getLogger(__name__)


def error_response(exc, default_message):
    """Always logs the full traceback (visible in `docker logs`).
    Only echoes the real exception message in the API response when
    DEBUG=True — in production you get the detail in your logs, not
    leaked to whoever's calling the API."""
    logger.exception(default_message)
    detail = str(exc) if settings.DEBUG else default_message
    return Response({'detail': detail}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class PostPagination(pagination.PageNumberPagination):
    page_size = 9
    page_size_query_param = 'page_size'
    max_page_size = 30


class PostViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/v1/news/posts/                       -> page 1, 9 posts
       GET /api/v1/news/posts/?page=2                 -> next page
       GET /api/v1/news/posts/?category=technology    -> filtered + paginated
       Public, read-only."""
    serializer_class = PostSerializer
    pagination_class = PostPagination
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Post.objects.filter(is_published=True)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__iexact=category)
        return qs

    def list(self, request, *args, **kwargs):
        try:
            return super().list(request, *args, **kwargs)
        except Exception as exc:
            return error_response(exc, 'Failed to list posts')

    def retrieve(self, request, *args, **kwargs):
        try:
            return super().retrieve(request, *args, **kwargs)
        except Exception as exc:
            return error_response(exc, 'Failed to retrieve post')


class GoogleAuthView(APIView):
    """POST /api/v1/news/auth/google/
       Body: {"credential": "<ID token from the Sign in with Google button>"}
       Verifies the token against Google directly (no session, no
       cookies). Every verified sign-in is recorded as a Subscriber.
       If the email is in settings.NEWS_ADMIN_EMAILS, a signed admin
       token is also issued for compose-page write access."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def post(self, request):
        credential = request.data.get('credential')
        if not credential:
            return Response({'detail': 'Missing credential'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            payload = google_id_token.verify_oauth2_token(
                credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
        except Exception as exc:
            logger.exception('Google token verification failed')
            return Response({'detail': 'Invalid Google credential'}, status=status.HTTP_401_UNAUTHORIZED)

        email = payload.get('email')
        name = payload.get('name', '')
        sub = payload.get('sub')

        if not payload.get('email_verified'):
            return Response({'detail': 'Google email is not verified'}, status=status.HTTP_401_UNAUTHORIZED)

        subscriber, created = Subscriber.objects.update_or_create(
            google_sub=sub, defaults={'email': email, 'name': name}
        )
        if created:
            send_thank_you_email.delay(subscriber.id)

        is_admin = email in settings.NEWS_ADMIN_EMAILS
        result = {'email': email, 'name': name, 'is_admin': is_admin}
        if is_admin:
            result['token'] = issue_admin_token(email)
        return Response(result)


class AdminPostViewSet(viewsets.ModelViewSet):
    """Full CRUD for the compose page. Mounted at
       /api/v1/news/admin/posts/ — requires a valid admin token from
       GoogleAuthView in the Authorization header."""
    queryset = Post.objects.all().order_by('-created_at')
    serializer_class = PostWriteSerializer
    authentication_classes = [SignedTokenAuthentication]
    permission_classes = [permissions.IsAdminUser]
    parser_classes = [parsers.MultiPartParser, parsers.FormParser, parsers.JSONParser]

    def create(self, request, *args, **kwargs):
        try:
            response = super().create(request, *args, **kwargs)
        except Exception as exc:
            return error_response(exc, 'Failed to create post')
        post = Post.objects.get(pk=response.data['id'])
        if post.is_published:
            send_push_for_post.delay(post.id)
        return response

    def update(self, request, *args, **kwargs):
        try:
            was_published = self.get_object().is_published
            response = super().update(request, *args, **kwargs)
        except Exception as exc:
            return error_response(exc, 'Failed to update post')
        post = Post.objects.get(pk=response.data['id'])
        if post.is_published and not was_published:
            send_push_for_post.delay(post.id)
        return response

    def destroy(self, request, *args, **kwargs):
        try:
            return super().destroy(request, *args, **kwargs)
        except Exception as exc:
            return error_response(exc, 'Failed to delete post')


class PushSubscriptionCreateView(generics.CreateAPIView):
    """POST /api/v1/news/push-subscriptions/
       Body is exactly what `pushSubscription.toJSON()` returns in the browser."""
    queryset = PushSubscription.objects.all()
    serializer_class = PushSubscriptionSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        try:
            return super().create(request, *args, **kwargs)
        except Exception as exc:
            return error_response(exc, 'Failed to create push subscription')


class NotificationEventUpdateView(generics.UpdateAPIView):
    """PATCH /api/v1/news/notification-events/<id>/
       Called by the service worker with {"status": "delivered"} or
       {"status": "clicked"}."""
    queryset = NotificationEvent.objects.all()
    serializer_class = NotificationEventSerializer
    permission_classes = [permissions.AllowAny]

    def perform_update(self, serializer):
        new_status = self.request.data.get('status')
        extra = {}
        if new_status == 'delivered':
            extra['delivered_at'] = timezone.now()
        elif new_status == 'clicked':
            extra['clicked_at'] = timezone.now()
        serializer.save(**extra)

    def update(self, request, *args, **kwargs):
        try:
            return super().update(request, *args, **kwargs)
        except Exception as exc:
            return error_response(exc, 'Failed to update notification event')


class SubscriberListView(generics.ListAPIView):
    """GET /api/v1/news/admin/subscribers/ — admin-only, read-only.
       Powers the 'Subscribers' tab in the compose page."""
    queryset = Subscriber.objects.all().order_by('-created_at')
    serializer_class = SubscriberSerializer
    authentication_classes = [SignedTokenAuthentication]
    permission_classes = [permissions.IsAdminUser]


class NewsletterSendView(APIView):
    """POST /api/v1/news/admin/newsletter/
       Body: {"post_ids": [1, 2], "subject": "...", "intro": "optional"}
       Bundles the given posts into one email and sends it to every
       subscribed Subscriber. Admin-only."""
    authentication_classes = [SignedTokenAuthentication]
    permission_classes = [permissions.IsAdminUser]

    def post(self, request):
        serializer = NewsletterSendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        posts = list(Post.objects.filter(id__in=data['post_ids'], is_published=True))
        if not posts:
            return Response({'detail': 'No matching published posts found'}, status=status.HTTP_400_BAD_REQUEST)

        recipient_count = Subscriber.objects.filter(is_subscribed=True).count()
        send_newsletter.delay(
            post_ids=[p.id for p in posts],
            subject=data['subject'],
            intro=data.get('intro', ''),
        )
        return Response({'queued': True, 'post_count': len(posts), 'recipient_count': recipient_count})


class UnsubscribeView(APIView):
    """GET /api/v1/news/unsubscribe/<token>/ — public, no auth. Every
       newsletter email links here with a per-subscriber signed token."""
    permission_classes = [permissions.AllowAny]
    authentication_classes = []

    def get(self, request, token):
        from django.core import signing
        try:
            data = signing.loads(token, salt='newsapp.unsubscribe', max_age=60 * 60 * 24 * 30)
        except signing.BadSignature:
            return Response({'detail': 'Invalid or expired unsubscribe link'}, status=status.HTTP_400_BAD_REQUEST)

        Subscriber.objects.filter(id=data.get('subscriber_id')).update(is_subscribed=False)
        return Response({'detail': 'You have been unsubscribed from DigitalTouch News emails.'})
