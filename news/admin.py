from django.contrib import admin
from django.utils import timezone

from .models import Post, PushSubscription, NotificationEvent
from .tasks import send_push_for_post


@admin.action(description='Publish selected posts and notify subscribers')
def publish_and_notify(modeladmin, request, queryset):
    for post in queryset:
        if not post.is_published:
            post.is_published = True
            post.published_at = timezone.now()
            post.save(update_fields=['is_published', 'published_at'])
        send_push_for_post.delay(post.id)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ['title', 'category', 'is_published', 'published_at', 'featured']
    list_filter = ['category', 'is_published']
    prepopulated_fields = {'slug': ('title',)}
    actions = [publish_and_notify]


@admin.register(PushSubscription)
class PushSubscriptionAdmin(admin.ModelAdmin):
    list_display = ['endpoint', 'is_active', 'created_at']
    list_filter = ['is_active']


@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ['post', 'subscription', 'status', 'sent_at', 'delivered_at', 'clicked_at']
    list_filter = ['status', 'post']

