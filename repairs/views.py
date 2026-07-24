from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone

from .models import Repair, RepairImage, RepairNote, RepairCost, RepairStatusLog
from .serializers import (
    RepairListSerializer, RepairDetailSerializer, BookingSerializer,
    StatusUpdateSerializer, RepairImageSerializer, RepairNoteSerializer, RepairCostSerializer,
)
from sms.tasks import send_status_sms


class BookingViewSet(viewsets.GenericViewSet):
    serializer_class = BookingSerializer
    permission_classes = [permissions.AllowAny]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repair = serializer.save()

        images = request.FILES.getlist("images")
        for img in images:
            RepairImage.objects.create(repair=repair, image=img, uploaded_by_staff=False)

        send_status_sms.delay(str(repair.id), repair.status)

        return Response(
            {"ref": repair.ref, "status": repair.status, "id": str(repair.id)},
            status=status.HTTP_201_CREATED,
        )


class RepairViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "assigned_to"]
    search_fields = ["ref", "client__first_name", "client__last_name", "client__phone"]
    ordering_fields = ["created_at", "updated_at", "status"]

    def get_queryset(self):
        return Repair.objects.select_related("client", "assigned_to").prefetch_related(
            "images", "costs", "notes", "status_logs"
        )

    def get_serializer_class(self):
        if self.action == "list":
            return RepairListSerializer
        return RepairDetailSerializer

    @action(detail=True, methods=["post"], url_path="status")
    def update_status(self, request, pk=None):
        repair = self.get_object()
        serializer = StatusUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        previous = repair.status
        new_status = serializer.validated_data["status"]
        note = serializer.validated_data.get("note", "")

        log = RepairStatusLog.objects.create(
            repair=repair,
            previous_status=previous,
            new_status=new_status,
            changed_by=request.user,
            note=note,
        )

        repair.status = new_status
        if new_status == "collected":
            repair.collected_at = timezone.now()
        repair.save(update_fields=["status", "updated_at", "collected_at"])

        send_status_sms.delay(str(repair.id), new_status, log_id=log.id)

        return Response({"detail": f"Status updated to {new_status}"})

    @action(detail=True, methods=["post"], url_path="images", parser_classes=[MultiPartParser, FormParser])
    def upload_image(self, request, pk=None):
        repair = self.get_object()
        images = request.FILES.getlist("images")
        if not images:
            return Response({"detail": "No images provided."}, status=status.HTTP_400_BAD_REQUEST)
        created = []
        for img in images:
            obj = RepairImage.objects.create(repair=repair, image=img, uploaded_by_staff=True)
            created.append(RepairImageSerializer(obj, context={"request": request}).data)
        return Response(created, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="notes")
    def add_note(self, request, pk=None):
        repair = self.get_object()
        serializer = RepairNoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(repair=repair, added_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="costs")
    def add_cost(self, request, pk=None):
        repair = self.get_object()
        serializer = RepairCostSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(repair=repair, added_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
