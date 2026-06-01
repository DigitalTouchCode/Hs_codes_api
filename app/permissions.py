from rest_framework.permissions import IsAuthenticated


class IsAdminOrStaff(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and request.user.role in (
            "Admin",
            "Staff",
        )
