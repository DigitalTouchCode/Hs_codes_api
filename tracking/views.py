from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from repairs.models import Repair
from repairs.serializers import RepairStatusLogSerializer


class TrackRepairView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, ref):
        try:
            repair = Repair.objects.prefetch_related("status_logs", "costs").get(ref=ref.upper())
        except Repair.DoesNotExist:
            return Response({"detail": "Repair not found."}, status=status.HTTP_404_NOT_FOUND)

        logs = RepairStatusLogSerializer(repair.status_logs.all(), many=True).data

        return Response({
            "ref": repair.ref,
            "device": f"{repair.device_brand} {repair.device_type}",
            "problem_description": repair.problem_description,
            "status": repair.status,
            "status_display": repair.get_status_display(),
            "estimated_completion": repair.estimated_completion,
            "total_cost": repair.total_cost,
            "created_at": repair.created_at,
            "timeline": logs,
        })
