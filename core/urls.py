from django.contrib import admin
from django.urls import path, include

from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls), 
    path("api/v1/", include("app.urls")),
    path("api/v1/events/", include("event.urls")),
    path("api/v1/news/", include("news.urls")),
    path("api/v1/pos/", include("pos.urls")),
    path("api/v1/crm/", include("clients.urls")),
    path("api/v1/repairs/", include("repairs.urls")),
    path("api/v1/track/", include("tracking.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
