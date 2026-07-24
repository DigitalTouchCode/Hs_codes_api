from rest_framework import serializers
from .models import Client, Testimonial


class ClientSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = Client
        fields = ["id", "first_name", "last_name", "full_name", "phone", "email", "created_at"]
        read_only_fields = ["id", "created_at"]


class TestimonialPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Testimonial
        fields = ["id", "display_name", "message", "rating", "created_at"]
        read_only_fields = ["id", "created_at"]


class TestimonialAdminSerializer(TestimonialPublicSerializer):
    class Meta(TestimonialPublicSerializer.Meta):
        fields = TestimonialPublicSerializer.Meta.fields + ["is_published", "client"]
