from dataclasses import asdict

from django.conf import settings
from django.contrib.postgres.search import TrigramSimilarity

from rest_framework import generics
from rest_framework.exceptions import ValidationError

from .models import HsCode

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
    # permission_classes = [IsAdminOrStaff]

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

    def get_queryset(self):
        try:
            q = self.request.query_params.get("q")

            if not q:
                logger.warning(
                    "Missing search query | path={path}",
                    path=self.request.path,
                )
                raise ValidationError({"q": ["This query parameter is required."]})

            threshold = getattr(
                settings,
                "HS_CODE_SEARCH_THRESHOLD",
                0.1,
            )

            logger.info(
                "HS search executed | query={q} | threshold={threshold}",
                q=q,
                threshold=threshold,
            )

            queryset = (
                HsCode.objects.annotate(
                    similarity=(
                        TrigramSimilarity("description", q) * 2
                        + TrigramSimilarity("hs_code", q)
                    )
                )
                .filter(similarity__gte=threshold)
                .order_by("-similarity")
            )

            logger.info(
                "HS search completed | query={q} | results={count}",
                q=q,
                count=queryset.count(),
            )
            
            logger.info(queryset)

            return queryset

        except Exception as e:
            logger.exception(
                "HS search failed | query={q} | error={error}",
                q=self.request.query_params.get("q"),
                error=str(e),
            )
            raise


class HealthCheckView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"status": "healthy"})
