from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Client, Testimonial
from .serializers import ClientSerializer, TestimonialPublicSerializer, TestimonialAdminSerializer


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    search_fields = ["first_name", "last_name", "phone", "email"]


class TestimonialViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Testimonial.objects.all()
        return Testimonial.objects.filter(is_published=True)

    def get_serializer_class(self):
        if self.request.user.is_authenticated:
            return TestimonialAdminSerializer
        return TestimonialPublicSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "create"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    def perform_create(self, serializer):
        serializer.save(is_published=False)
