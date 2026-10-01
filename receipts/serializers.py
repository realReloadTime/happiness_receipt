from rest_framework import serializers

from .models import Receipt


class ReceiptSerializer(serializers.ModelSerializer):
    """Сериализатор чека для GET /api/receipts/."""

    status_display = serializers.CharField(source="get_status_display", read_only=True)
    amount = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=False)

    class Meta:
        model = Receipt
        fields = [
            "id",
            "fn",
            "fd",
            "fp",
            "purchased_at",
            "amount",
            "status",
            "status_display",
            "rejection_reason",
            "photo",
            "created_at",
        ]
        read_only_fields = fields