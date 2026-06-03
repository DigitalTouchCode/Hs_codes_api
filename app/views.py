from dataclasses import asdict

from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity

from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .models import HsCode
from django.db.models import Q

from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsAdminOrStaff
from .serializers import HsCodeUploadSerializer, HsCodeSerializer
from .services.file_upload_service import process_hs_code_csv
from loguru import logger


class HsCodeUploadView(APIView):
    parser_classes = [MultiPartParser]
    authentication_classes = []
    permission_classes = []

    def post(self, request):
        serializer = HsCodeUploadSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = process_hs_code_csv(
                uploaded_file=serializer.validated_data["file"]
            )
        except ValueError as exc:
            logger.error("Failed to process file:{}", str(exc))
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(asdict(result), status=status.HTTP_201_CREATED)


class HsCodeSearchView(generics.ListAPIView):
    serializer_class = HsCodeSerializer
    authentication_classes = []
    permission_classes = []
    
    def get_queryset(self):
      q = self.request.query_params.get("q", "").strip()

      if not q:
        raise ValidationError({"q": ["This query parameter is required."]})

      exact_qs = HsCode.objects.filter(
        Q(description__icontains=q) | Q(hs_code__icontains=q)
       )

      if exact_qs.exists():
        logger.info("HS search (exact) | query={q}", q=q)
        return exact_qs.order_by("hs_code")

      threshold = getattr(settings, "HS_CODE_SEARCH_THRESHOLD", 0.3)

      queryset = (
        HsCode.objects.annotate(
            similarity=TrigramSimilarity("description", q)
        )
        .filter(similarity__gte=threshold)
        .order_by("-similarity")
      )

      logger.info(
        "HS search (fuzzy) | query={q} | threshold={threshold}",
        q=q, threshold=threshold,
      )
      return queryset


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "healthy"})
