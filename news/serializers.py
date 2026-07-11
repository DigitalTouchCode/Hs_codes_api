import bleach
from django.utils import timezone
from rest_framework import serializers
from .models import Post, PushSubscription, NotificationEvent, Subscriber

ALLOWED_TAGS = ['b', 'strong', 'i', 'em', 'u', 'a', 'ul', 'ol', 'li', 'br']
ALLOWED_ATTRS = {'a': ['href', 'target', 'rel']}


def sanitize_paragraph(html):
    return bleach.clean(html, tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)


class PostSerializer(serializers.ModelSerializer):
    """Public, read-only — what news.html actually consumes."""
    date = serializers.DateTimeField(source='published_at', format='%Y-%m-%d', read_only=True)
    category = serializers.SerializerMethodField()
    image = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'category', 'excerpt', 'content', 'image', 'featured', 'date']

    def get_category(self, obj):
        # Returns the human-readable label ("Technology") to match the
        # frontend's CATEGORY_ORDER exactly.
        return obj.get_category_display()

    def get_image(self, obj):
        if not obj.image:
            return None
        request = self.context.get('request')
        url = obj.image.url
        return request.build_absolute_uri(url) if request else url


class PostWriteSerializer(serializers.ModelSerializer):
    """Admin-only — full read/write, used by the compose page. `category`
    here is the raw choice value ('technology'), matching a <select>'s
    option values, not the display label. `image` accepts an uploaded
    file via multipart/form-data."""

    # binary=True makes this parse a JSON string into a real list — needed
    # because multipart/form-data (used for the image upload) sends every
    # field as plain text, unlike a JSON request body.
    content = serializers.JSONField(binary=True)

    class Meta:
        model = Post
        fields = ['id', 'title', 'slug', 'category', 'excerpt', 'content', 'image', 'featured', 'is_published', 'published_at']
        read_only_fields = ['id']

    def create(self, validated_data):
        if 'content' in validated_data:
            validated_data['content'] = [sanitize_paragraph(p) for p in validated_data['content']]
        if validated_data.get('is_published') and not validated_data.get('published_at'):
            validated_data['published_at'] = timezone.now()
        return super().create(validated_data)

    def update(self, instance, validated_data):
        if 'content' in validated_data:
            validated_data['content'] = [sanitize_paragraph(p) for p in validated_data['content']]
        # Publishing for the first time stamps published_at now, even if
        # the post was drafted days earlier.
        if validated_data.get('is_published') and not instance.published_at:
            validated_data['published_at'] = timezone.now()
        return super().update(instance, validated_data)


class PushSubscriptionSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = PushSubscription
        fields = ['id', 'endpoint', 'p256dh', 'auth', 'session_id', 'email']

    def create(self, validated_data):
        email = validated_data.pop('email', None)
        subscriber = None
        if email:
            subscriber, _ = Subscriber.objects.get_or_create(email=email)
        # Re-subscribing with the same endpoint just reactivates it rather
        # than creating a duplicate row.
        obj, _ = PushSubscription.objects.update_or_create(
            endpoint=validated_data['endpoint'],
            defaults={**validated_data, 'is_active': True, 'subscriber': subscriber},
        )
        return obj


class NotificationEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationEvent
        fields = ['id', 'status', 'sent_at', 'delivered_at', 'clicked_at']
        read_only_fields = ['sent_at']


class SubscriberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subscriber
        fields = ['id', 'email', 'name', 'is_subscribed', 'created_at']


class NewsletterSendSerializer(serializers.Serializer):
    post_ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False)
    subject = serializers.CharField(max_length=200)
    intro = serializers.CharField(required=False, allow_blank=True, default='')

