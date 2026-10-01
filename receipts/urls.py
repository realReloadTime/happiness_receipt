from django.urls import path

from . import views
from .api_views import ReceiptListAPIView

app_name = "receipts"

urlpatterns = [
    path("", views.cabinet, name="cabinet"),
    path("receipts/register/", views.register_receipt, name="register_receipt"),
    path("api/receipts/", ReceiptListAPIView.as_view(), name="api_receipts"),
]