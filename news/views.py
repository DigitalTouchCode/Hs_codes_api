from django.utils import timezone
from rest_framework import viewsets, generics, permissions

from .models import Post, PushSubscription, NotificationEvent
from .serializers import PostSerializer, PushSubscriptionSerializer, NotificationEventSerializer


class PostViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /api/v1/news/posts/            -> all published posts
       GET /api/v1/news/posts/?category=technology -> filtered"""
    serializer_class = PostSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        qs = Post.objects.filter(is_published=True)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__iexact=category)
        return qs


class PushSubscriptionCreateView(generics.CreateAPIView):
    """POST /api/v1/news/push-subscriptions/
       Body is exactly what `pushSubscription.toJSON()` returns in the browser."""
    queryset = PushSubscription.objects.all()
    serializer_class = PushSubscriptionSerializer
    permission_classes = [permissions.AllowAny]


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

