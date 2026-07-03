import logging

from django.conf import settings
from django.utils import timezone
from rest_framework import viewsets, generics, permissions, pagination
from rest_framework.response import Response
from rest_framework import status

from .models import Post, PushSubscription, NotificationEvent
from .serializers import PostSerializer, PushSubscriptionSerializer, NotificationEventSerializer

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
       Response shape: {"count", "next", "previous", "results"} — the
       frontend's infinite scroll follows `next` directly, so pagination
       params never need to be constructed by hand on either side."""
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


