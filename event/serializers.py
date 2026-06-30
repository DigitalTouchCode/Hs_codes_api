from rest_framework import serializers
from .models import Event


class EventCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Event
        fields = ["tool", "action", "session_id", "metadata"]

    def validate_session_id(self, value):
        if not value or len(value) < 8:
            raise serializers.ValidationError("session_id must be a reasonably random string.")
        return value
