from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils.text import slugify
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from loguru import logger
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import PosProfile, Tenant
from .serializers import (
    GoogleAuthSerializer, LoginSerializer, PosProfileSerializer, SignupSerializer, unique_slug_for,
)

User = get_user_model()


def tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"access": str(refresh.access_token), "refresh": str(refresh)}


class SignupView(APIView):
    """POST /api/v1/pos/auth/signup/
       Body: {business_name, name, email, password}
       Creates a new Tenant + PosProfile (role=admin) for a brand-new business."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        return Response(
            {"user": PosProfileSerializer(user.posprofile).data, "tokens": tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    """POST /api/v1/pos/auth/login/
       Body: {email, password}"""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        password = serializer.validated_data["password"]

        user = User.objects.filter(email__iexact=email).first()
        if not user or not user.has_usable_password() or not user.check_password(password):
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)
        if not user.is_active:
            return Response({"detail": "This account has been deactivated."}, status=status.HTTP_403_FORBIDDEN)
        if not hasattr(user, "posprofile"):
            return Response({"detail": "This account has no POS access."}, status=status.HTTP_403_FORBIDDEN)

        return Response({"user": PosProfileSerializer(user.posprofile).data, "tokens": tokens_for_user(user)})


class GoogleAuthView(APIView):
    """POST /api/v1/pos/auth/google/
       Body: {credential} — same field name as news.GoogleAuthView, since
       both consume the same Google Identity Services response shape.

       If the Google account already has a PosProfile, logs them in.
       Otherwise creates a brand-new Tenant + admin PosProfile, same as
       SignupView, using `business_name` from the request if supplied."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = GoogleAuthSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        credential = serializer.validated_data["credential"]

        try:
            payload = google_id_token.verify_oauth2_token(
                credential, google_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
        except Exception:
            logger.exception("Google token verification failed (pos)")
            return Response({"detail": "Invalid Google credential"}, status=status.HTTP_401_UNAUTHORIZED)

        google_sub = payload.get("sub")
        email = (payload.get("email") or "").lower()
        email_verified = bool(payload.get("email_verified"))
        name = payload.get("name") or (email.split("@")[0] if email else "")

        if not email or not email_verified:
            return Response({"detail": "Google account has no verified email."}, status=status.HTTP_400_BAD_REQUEST)

        profile = PosProfile.objects.filter(google_sub=google_sub).select_related("user").first()
        if not profile:
            existing_user = User.objects.filter(email__iexact=email).first()
            if existing_user and hasattr(existing_user, "posprofile"):
                profile = existing_user.posprofile

        if profile:
            if not profile.google_sub:
                profile.google_sub = google_sub
                profile.save(update_fields=["google_sub"])
            if not profile.user.is_active:
                return Response({"detail": "This account has been deactivated."}, status=status.HTTP_403_FORBIDDEN)
            return Response({"user": PosProfileSerializer(profile).data, "tokens": tokens_for_user(profile.user)})

        # First time we've seen this Google account for POS — new tenant + admin
        business_name = serializer.validated_data.get("business_name") or f"{name}'s Business"
        tenant = Tenant.objects.create(name=business_name, slug=unique_slug_for(business_name))

        user = User.objects.filter(email__iexact=email).first()
        if not user:
            user = User.objects.create_user(username=email, email=email, first_name=name)
            user.set_unusable_password()
            user.save()

        profile = PosProfile.objects.create(
            user=user, tenant=tenant, role=PosProfile.ROLE_ADMIN, google_sub=google_sub,
        )
        return Response(
            {"user": PosProfileSerializer(profile).data, "tokens": tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not hasattr(request.user, "posprofile"):
            return Response({"detail": "This account has no POS access."}, status=status.HTTP_403_FORBIDDEN)
        return Response(PosProfileSerializer(request.user.posprofile).data)
