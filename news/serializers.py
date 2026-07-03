from rest_framework import serializers
from .models import Post, PushSubscription, NotificationEvent


class PostSerializer(serializers.ModelSerializer):
    date = serializers.DateField(source='published_at', format='%Y-%m-%d', read_only=True)
    category = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'category', 'excerpt', 'content', 'featured', 'date']

    def get_category(self, obj):
        # Returns the human-readable label ("Technology") to match the
        # frontend's CATEGORY_ORDER exactly.
        return obj.get_category_display()


class PushSubscriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PushSubscription
        fields = ['id', 'endpoint', 'p256dh', 'auth', 'session_id']

    def create(self, validated_data):
        # Re-subscribing with the same endpoint just reactivates it rather
        # than creating a duplicate row.
        obj, _ = PushSubscription.objects.update_or_create(
            endpoint=validated_data['endpoint'],
            defaults={**validated_data, 'is_active': True},
        )
        return obj


class NotificationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationEvent
        fields = ['id', 'status', 'sent_at', 'delivered_at', 'clicked_at']
        read_only_fields = ['sent_at']

