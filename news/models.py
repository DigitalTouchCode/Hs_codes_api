from django.db import models


class Post(models.Model):
    """A single news/blog post. `category` matches the classic taxonomy
    used on the frontend filter tabs, so no mapping layer is needed."""

    CATEGORY_CHOICES = [
        ('announcements', 'Announcements'),
        ('technology', 'Technology'),
        ('compliance', 'Compliance'),
        ('business', 'Business'),
        ('company', 'Company'),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    excerpt = models.CharField(max_length=300)
    content = models.JSONField(help_text="List of paragraph strings, rendered as-is on the frontend")
    image = models.ImageField(upload_to='news/%Y/%m/', blank=True, null=True)
    featured = models.BooleanField(default=False)
    is_published = models.BooleanField(default=False)
    published_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_at']

    def __str__(self):
        return self.title


class Subscriber(models.Model):
    """A person identified via Google Sign-In. Linking push subscriptions
    to a real identity (rather than an anonymous browser endpoint) means
    you can see who's actually subscribed, not just how many devices."""
    email = models.EmailField(unique=True)
    google_sub = models.CharField(max_length=64, unique=True, null=True, blank=True)
    name = models.CharField(max_length=150, blank=True)
    is_subscribed = models.BooleanField(default=True, help_text="False once they unsubscribe from newsletter emails")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.email


class PushSubscription(models.Model):
    """One browser push endpoint. Created when a visitor taps
    'Enable notifications' and the frontend POSTs the PushSubscription
    object it got back from the browser's Push API."""

    endpoint = models.URLField(max_length=500, unique=True)
    p256dh = models.CharField(max_length=200)
    auth = models.CharField(max_length=100)
    session_id = models.CharField(max_length=100, blank=True, null=True)
    subscriber = models.ForeignKey(Subscriber, on_delete=models.SET_NULL, null=True, blank=True, related_name='push_subscriptions')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.endpoint[:60]


class NotificationEvent(models.Model):
    """One row per (subscription, post) push attempt. Created with
    status='sent' the moment a push is dispatched; the service worker
    PATCHes it to 'delivered' once the browser shows it, and to
    'clicked' if the person taps it. This is the honest, trackable
    lifecycle — there's no browser signal for 'the person actually read
    it', only reached-the-device and engaged-with-it."""

    STATUS_CHOICES = [
        ('sent', 'Sent'),
        ('delivered', 'Delivered'),
        ('clicked', 'Clicked'),
    ]

    subscription = models.ForeignKey(PushSubscription, on_delete=models.CASCADE, related_name='events')
    post = models.ForeignKey(Post, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='sent')
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"post={self.post_id} sub={self.subscription_id} ({self.status})"
