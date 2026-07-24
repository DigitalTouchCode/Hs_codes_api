from rest_framework import serializers
from .models import Repair, RepairImage, RepairStatusLog, RepairNote, RepairCost


class RepairImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairImage
        fields = ["id", "image", "uploaded_at", "uploaded_by_staff"]
        read_only_fields = ["id", "uploaded_at"]


class RepairCostSerializer(serializers.ModelSerializer):
    added_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = RepairCost
        fields = ["id", "description", "amount", "added_by", "created_at"]
        read_only_fields = ["id", "added_by", "created_at"]


class RepairNoteSerializer(serializers.ModelSerializer):
    added_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = RepairNote
        fields = ["id", "content", "is_internal", "added_by", "created_at"]
        read_only_fields = ["id", "added_by", "created_at"]


class RepairStatusLogSerializer(serializers.ModelSerializer):
    changed_by = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = RepairStatusLog
        fields = ["id", "previous_status", "new_status", "changed_by", "note", "sms_sent", "created_at"]
        read_only_fields = ["id", "changed_by", "sms_sent", "created_at"]


class RepairListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.full_name", read_only=True)
    client_phone = serializers.CharField(source="client.phone", read_only=True)
    total_cost = serializers.ReadOnlyField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Repair
        fields = [
            "id", "ref", "client_name", "client_phone",
            "device_type", "device_brand", "device_model",
            "status", "status_display", "total_cost",
            "assigned_to", "created_at", "estimated_completion",
        ]


class RepairDetailSerializer(serializers.ModelSerializer):
    images = RepairImageSerializer(many=True, read_only=True)
    costs = RepairCostSerializer(many=True, read_only=True)
    notes = RepairNoteSerializer(many=True, read_only=True)
    status_logs = RepairStatusLogSerializer(many=True, read_only=True)
    total_cost = serializers.ReadOnlyField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    client_name = serializers.CharField(source="client.full_name", read_only=True)
    client_phone = serializers.CharField(source="client.phone", read_only=True)

    class Meta:
        model = Repair
        fields = [
            "id", "ref", "client", "client_name", "client_phone",
            "device_type", "device_brand", "device_model", "serial_number",
            "problem_description", "status", "status_display",
            "assigned_to", "estimated_completion", "collected_at",
            "total_cost", "images", "costs", "notes", "status_logs",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "ref", "created_at", "updated_at"]


class BookingSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(write_only=True)
    last_name = serializers.CharField(write_only=True)
    phone = serializers.CharField(write_only=True)
    email = serializers.EmailField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Repair
        fields = [
            "first_name", "last_name", "phone", "email",
            "device_type", "device_brand", "device_model",
            "serial_number", "problem_description",
            "ref", "status", "created_at",
        ]
        read_only_fields = ["ref", "status", "created_at"]

    def create(self, validated_data):
        from clients.models import Client
        first_name = validated_data.pop("first_name")
        last_name = validated_data.pop("last_name")
        phone = validated_data.pop("phone")
        email = validated_data.pop("email", "")

        client, _ = Client.objects.get_or_create(
            phone=phone,
            defaults={"first_name": first_name, "last_name": last_name, "email": email},
        )
        return Repair.objects.create(client=client, **validated_data)


class StatusUpdateSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Repair.status.field.choices)
    note = serializers.CharField(required=False, allow_blank=True)
