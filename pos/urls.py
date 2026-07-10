from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .auth import GoogleAuthView, LoginView, MeView, SignupView
from .sync import SyncPullView, SyncPushView

urlpatterns = [
    path("auth/signup/", SignupView.as_view(), name="pos-signup"),
    path("auth/login/", LoginView.as_view(), name="pos-login"),
    path("auth/google/", GoogleAuthView.as_view(), name="pos-google-auth"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="pos-token-refresh"),
    path("auth/me/", MeView.as_view(), name="pos-me"),
    path("sync/pull/", SyncPullView.as_view(), name="pos-sync-pull"),
    path("sync/push/", SyncPushView.as_view(), name="pos-sync-push"),
]
