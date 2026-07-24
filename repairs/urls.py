from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RepairViewSet, BookingViewSet

router = DefaultRouter()
router.register("booking", BookingViewSet, basename="booking")
router.register("", RepairViewSet, basename="repair")

urlpatterns = [path("", include(router.urls))]
