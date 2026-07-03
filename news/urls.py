from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import PostViewSet, PushSubscriptionCreateView, NotificationEventUpdateView

router = DefaultRouter()
router.register('posts', PostViewSet, basename='post')

urlpatterns = [
    path('', include(router.urls)),
    path('push-subscriptions/', PushSubscriptionCreateView.as_view(), name='push-subscribe'),
    path('notification-events/<int:pk>/', NotificationEventUpdateView.as_view(), name='notification-event-update'),
]


