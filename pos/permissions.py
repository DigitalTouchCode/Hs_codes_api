from rest_framework.permissions import BasePermission


class IsPosMember(BasePermission):
    """Must be authenticated and have a PosProfile (i.e. actually part of a POS tenant —
    not just any logged-in user of this shared Django project)."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and hasattr(request.user, "posprofile"))


def HasPosRole(*roles):
    """
    Factory for a role-restricted permission class, matching the frontend's
    ROLE_TABS split (admin / manager / sales).

        class ProductViewSet(viewsets.ModelViewSet):
            permission_classes = [IsPosMember, HasPosRole("admin", "manager")]
    """

    class _RolePermission(BasePermission):
        def has_permission(self, request, view):
            profile = getattr(request.user, "posprofile", None)
            return bool(profile and profile.role in roles)

    return _RolePermission


class TenantScopedQuerysetMixin:
    """Scopes every list/detail query to request.user.posprofile.tenant — the
    single most important guardrail for keeping one business's data from
    ever leaking into another's."""

    def get_queryset(self):
        return super().get_queryset().filter(tenant=self.request.user.posprofile.tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.user.posprofile.tenant)
