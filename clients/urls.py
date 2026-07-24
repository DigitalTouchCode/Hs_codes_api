from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ClientViewSet, TestimonialViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("testimonials", TestimonialViewSet, basename="testimonial")

urlpatterns = [path("", include(router.urls))]
