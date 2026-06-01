from dataclasses import asdict

from rest_framework import status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from .permissions import IsAdminOrStaff
from .serializers import HsCodeUploadSerializer
from .services.file_upload_service import process_hs_code_csv


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
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(asdict(result), status=status.HTTP_201_CREATED)
