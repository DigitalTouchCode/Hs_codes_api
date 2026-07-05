from django.urls import path
from .views import EventCreateView

urlpatterns = [
    path("", EventCreateView.as_view(), name="event-create"),
]
