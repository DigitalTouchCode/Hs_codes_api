from django.conf import settings
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.text import slugify
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from loguru import logger
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .models import (
    ActivityLog, Branch, Customer, Expense, PosInvite, PosProfile, Product, ProductStock,
    Purchase, Return, Sale, Tenant,
)
from .permissions import HasPosRole, IsPosMember, TenantScopedQuerysetMixin
from .serializers import (
    ActivityLogSerializer, BranchSerializer, CustomerSerializer, DirectUserCreateSerializer,
    ExpenseSerializer, GoogleAuthSerializer, InviteAcceptSerializer, InviteCreateSerializer,
    InvitePublicSerializer, LoginSerializer, PosProfileSerializer, ProductSerializer,
    ProductStockSerializer, PurchaseSerializer, ReturnSerializer, RosterEntrySerializer,
    SaleSerializer, SignupSerializer, unique_slug_for,
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


# ---------------------------------------------------------------------------
# Invites & roster
#
# Adding a teammate has two paths from Settings > Users & roles:
#   - Invite by email: admin picks role/branch, we hand back a link
#     containing a token; the invitee opens it, sets their own name and
#     password (InviteAcceptView), and gets a real login. No email is sent
#     server-side — the admin shares the link the same way receipts already
#     get shared, over WhatsApp/etc.
#   - Add user with password: admin sets the password directly and the
#     teammate can log in immediately, no separate acceptance step.
# Both are restricted to admins of the tenant.
# ---------------------------------------------------------------------------

class InviteCreateView(APIView):
    """POST /api/v1/pos/auth/invite/  (admin)
       Body: {email, role, branch} -> {token, email, role, branch, expires_at}"""

    permission_classes = [IsAuthenticated, IsPosMember, HasPosRole(PosProfile.ROLE_ADMIN)]

    def post(self, request):
        serializer = InviteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite = PosInvite.objects.create(
            tenant=request.user.posprofile.tenant,
            invited_by=request.user,
            **serializer.validated_data,
        )
        return Response(
            {
                "token": invite.token,
                "email": invite.email,
                "role": invite.role,
                "branch": invite.branch_id,
                "expires_at": invite.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )


class InviteDetailView(APIView):
    """GET /api/v1/pos/auth/invite/<token>/  (public)
       Lets the invite-accept screen show "you're joining X as a Y" before
       the person creates a password."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, token):
        invite = PosInvite.objects.filter(token=token).select_related("tenant").first()
        if not invite or invite.status != PosInvite.STATUS_PENDING or invite.is_expired:
            return Response({"detail": "This invite link isn't valid or has expired."}, status=status.HTTP_404_NOT_FOUND)
        return Response(InvitePublicSerializer(invite).data)


class InviteAcceptView(APIView):
    """POST /api/v1/pos/auth/invite/accept/  (public)
       Body: {token, name, password} -> {tokens, user}, same shape as login/signup."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        serializer = InviteAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.validated_data["token"]

        invite = PosInvite.objects.filter(token=token).select_related("tenant").first()
        if not invite or invite.status != PosInvite.STATUS_PENDING or invite.is_expired:
            return Response({"detail": "This invite link isn't valid or has expired."}, status=status.HTTP_400_BAD_REQUEST)
        if User.objects.filter(email__iexact=invite.email).exists():
            return Response({"detail": "An account with this email already exists."}, status=status.HTTP_400_BAD_REQUEST)

        user = User.objects.create_user(
            username=invite.email,
            email=invite.email,
            password=serializer.validated_data["password"],
            first_name=serializer.validated_data["name"],
        )
        profile = PosProfile.objects.create(
            user=user, tenant=invite.tenant, role=invite.role, branch_id=invite.branch_id,
        )
        invite.status = PosInvite.STATUS_ACCEPTED
        invite.accepted_at = timezone.now()
        invite.save(update_fields=["status", "accepted_at"])

        return Response(
            {"user": PosProfileSerializer(profile).data, "tokens": tokens_for_user(user)},
            status=status.HTTP_201_CREATED,
        )


class UsersView(APIView):
    """GET  /api/v1/pos/auth/users/  (admin or manager) — roster: active
         PosProfiles plus outstanding PosInvites for this tenant, so
         Settings > Users & roles reflects real server state instead of
         only what happened in this browser.
       POST /api/v1/pos/auth/users/  (admin) — {name, email, password, role,
         branch} -> {user}. Creates a real login immediately, no
         acceptance step (the alternative to inviting by email)."""

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticated(), IsPosMember(), HasPosRole(PosProfile.ROLE_ADMIN)()]
        return [IsAuthenticated(), IsPosMember(), HasPosRole(PosProfile.ROLE_ADMIN, PosProfile.ROLE_MANAGER)()]

    def get(self, request):
        tenant = request.user.posprofile.tenant
        active = [
            {
                "id": profile.user.email,
                "name": profile.user.first_name or profile.user.email,
                "email": profile.user.email,
                "role": profile.role,
                "branch_id": profile.branch_id,
                "status": "active",
            }
            for profile in PosProfile.objects.filter(tenant=tenant).select_related("user")
        ]
        invited = [
            {
                "id": f"invite:{invite.id}",
                "name": invite.email,
                "email": invite.email,
                "role": invite.role,
                "branch_id": invite.branch_id,
                "status": "invited",
            }
            for invite in PosInvite.objects.filter(tenant=tenant, status=PosInvite.STATUS_PENDING)
            if not invite.is_expired
        ]
        roster = RosterEntrySerializer(active + invited, many=True).data
        return Response(roster)

    def post(self, request):
        serializer = DirectUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = User.objects.create_user(
            username=data["email"], email=data["email"], password=data["password"], first_name=data["name"],
        )
        profile = PosProfile.objects.create(
            user=user, tenant=request.user.posprofile.tenant, role=data["role"], branch_id=data.get("branch_id"),
        )
        return Response({"user": PosProfileSerializer(profile).data}, status=status.HTTP_201_CREATED)


# ---------------------------------------------------------------------------
# CRUD viewsets for direct querying/management outside the sync flow (a
# reporting dashboard, admin tooling, future integrations). The POS
# terminal itself should keep using /sync/pull/ and /sync/push/, which
# handle offline queuing, stock deltas, and conflict resolution; these
# viewsets are a plain, standard DRF surface on top of the same tenant-
# scoped models for everything else.
#
# Read/write split matches the frontend's ROLE_TABS exactly: Sales can see
# products and customers (they need that to ring up a sale and process
# returns) but can't create/edit them; Purchases/Expenses/Logs are hidden
# from Sales entirely, matching the frontend nav.
# ----------------------
class TenantScopedReadWriteViewSet(TenantScopedQuerysetMixin, viewsets.ModelViewSet):
    """Read is open to any POS member of the tenant; write (create/update/
    destroy) is restricted to `write_roles`. Subclasses set `write_roles`."""

    permission_classes = [IsAuthenticated, IsPosMember]
    write_roles = (PosProfile.ROLE_ADMIN,)

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsPosMember(), HasPosRole(*self.write_roles)()]
        return [IsAuthenticated(), IsPosMember()]


class TenantScopedReadOnlyViewSet(TenantScopedQuerysetMixin, viewsets.ReadOnlyModelViewSet):
    """Ledger data (sales, returns, purchases, expenses, logs) is never
    created or edited through this API only via /sync/push/, which also
    applies the stock delta. Exposing a write endpoint here would let
    someone create a Sale without that side effect running, silently
    corrupting stock. `read_roles = None` means any POS member can read."""

    permission_classes = [IsAuthenticated, IsPosMember]
    read_roles = None

    def get_permissions(self):
        if self.read_roles:
            return [IsAuthenticated(), IsPosMember(), HasPosRole(*self.read_roles)()]
        return [IsAuthenticated(), IsPosMember()]


class BranchViewSet(TenantScopedReadWriteViewSet):
    queryset = Branch.objects.filter(is_deleted=False)
    serializer_class = BranchSerializer
    write_roles = (PosProfile.ROLE_ADMIN,)


class ProductViewSet(TenantScopedReadWriteViewSet):
    queryset = Product.objects.filter(is_deleted=False)
    serializer_class = ProductSerializer
    write_roles = (PosProfile.ROLE_ADMIN, PosProfile.ROLE_MANAGER)


class ProductStockViewSet(TenantScopedReadWriteViewSet):
    queryset = ProductStock.objects.filter(is_deleted=False)
    serializer_class = ProductStockSerializer
    write_roles = (PosProfile.ROLE_ADMIN, PosProfile.ROLE_MANAGER)


class CustomerViewSet(TenantScopedReadWriteViewSet):
    queryset = Customer.objects.filter(is_deleted=False)
    serializer_class = CustomerSerializer
    # Every role can add/edit customers — matches the frontend, where Sales
    # can add a walk-in customer straight from the POS cart.
    write_roles = (PosProfile.ROLE_ADMIN, PosProfile.ROLE_MANAGER, PosProfile.ROLE_SALES)


class SaleViewSet(TenantScopedReadOnlyViewSet):
    queryset = Sale.objects.filter(is_deleted=False).prefetch_related("items")
    serializer_class = SaleSerializer
    # Sales needs sale history to look up a receipt when processing a return.


class ReturnViewSet(TenantScopedReadOnlyViewSet):
    queryset = Return.objects.filter(is_deleted=False).prefetch_related("items")
    serializer_class = ReturnSerializer


class PurchaseViewSet(TenantScopedReadOnlyViewSet):
    queryset = Purchase.objects.filter(is_deleted=False)
    serializer_class = PurchaseSerializer
    read_roles = (PosProfile.ROLE_ADMIN, PosProfile.ROLE_MANAGER)


class ExpenseViewSet(TenantScopedReadOnlyViewSet):
    queryset = Expense.objects.filter(is_deleted=False)
    serializer_class = ExpenseSerializer
    read_roles = (PosProfile.ROLE_ADMIN, PosProfile.ROLE_MANAGER)


class ActivityLogViewSet(TenantScopedReadOnlyViewSet):
    queryset = ActivityLog.objects.all()
    serializer_class = ActivityLogSerializer
    read_roles = (PosProfile.ROLE_ADMIN, PosProfile.ROLE_MANAGER)
