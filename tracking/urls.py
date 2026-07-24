from django.urls import path
from .views import TrackRepairView

urlpatterns = [
    path("<str:ref>/", TrackRepairView.as_view(), name="track-repair"),
]
