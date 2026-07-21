from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .sync import SyncPullView, SyncPushView
from .views import (
    ActivityLogViewSet, BranchViewSet, CustomerViewSet, ExpenseViewSet,
    GoogleAuthView, InviteAcceptView, InviteCreateView, InviteDetailView,
    LoginView, MeView, ProductStockViewSet, ProductViewSet, PurchaseViewSet,
    ReturnViewSet, SaleViewSet, SignupView, UsersView,
)

router = DefaultRouter()
router.register("branches", BranchViewSet, basename="pos-branch")
router.register("products", ProductViewSet, basename="pos-product")
router.register("product-stock", ProductStockViewSet, basename="pos-product-stock")
router.register("customers", CustomerViewSet, basename="pos-customer")
router.register("sales", SaleViewSet, basename="pos-sale")
router.register("returns", ReturnViewSet, basename="pos-return")
router.register("purchases", PurchaseViewSet, basename="pos-purchase")
router.register("expenses", ExpenseViewSet, basename="pos-expense")
router.register("logs", ActivityLogViewSet, basename="pos-log")

urlpatterns = [
    path("auth/signup/", SignupView.as_view(), name="pos-signup"),
    path("auth/login/", LoginView.as_view(), name="pos-login"),
    path("auth/google/", GoogleAuthView.as_view(), name="pos-google-auth"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="pos-token-refresh"),
    path("auth/me/", MeView.as_view(), name="pos-me"),
    path("auth/invite/", InviteCreateView.as_view(), name="pos-invite-create"),
    path("auth/invite/accept/", InviteAcceptView.as_view(), name="pos-invite-accept"),
    path("auth/invite/<str:token>/", InviteDetailView.as_view(), name="pos-invite-detail"),
    path("auth/users/", UsersView.as_view(), name="pos-users"),
    path("sync/pull/", SyncPullView.as_view(), name="pos-sync-pull"),
    path("sync/push/", SyncPushView.as_view(), name="pos-sync-push"),
    path("", include(router.urls)),
]
