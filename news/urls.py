from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    PostViewSet, PushSubscriptionCreateView, NotificationEventUpdateView,
    GoogleAuthView, AdminPostViewSet,
)

router = DefaultRouter()
router.register('posts', PostViewSet, basename='post')
router.register('admin/posts', AdminPostViewSet, basename='admin-post')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/google/', GoogleAuthView.as_view(), name='google-auth'),
    path('push-subscriptions/', PushSubscriptionCreateView.as_view(), name='push-subscribe'),
    path('notification-events/<int:pk>/', NotificationEventUpdateView.as_view(), name='notification-event-update'),
]
