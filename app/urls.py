from django.urls import path
from .views import HsCodeUploadView

urlpatterns = [
    path("hs-codes/upload/", HsCodeUploadView.as_view(), name="hscode-upload"),
]
