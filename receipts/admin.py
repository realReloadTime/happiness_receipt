import csv

from django import forms
from django.contrib import admin
from django.http import HttpResponse
from django.utils.html import format_html

from .models import Receipt


class ReceiptAdminForm(forms.ModelForm):
    class Meta:
        model = Receipt
        fields = "__all__"

    def clean(self):
        cleaned = super().clean()
        status = cleaned.get("status")
        reason = cleaned.get("rejection_reason")
        if status == Receipt.Status.REJECTED and not (reason or "").strip():
            self.add_error("rejection_reason", "Укажите причину отказа.")
        if status != Receipt.Status.REJECTED and reason:
            cleaned["rejection_reason"] = ""
        return cleaned


@admin.action(description="Выгрузить принятые чеки в CSV")
def export_accepted_csv(modeladmin, request, queryset):
    """Выгрузка принятых чеков в CSV (с BOM для корректного открытия в Excel)."""
    queryset = queryset.filter(status=Receipt.Status.ACCEPTED)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="accepted_receipts.csv"'
    response.write("\ufeff")

    writer = csv.writer(response)
    writer.writerow(
        [
            "Пользователь",
            "ФН",
            "ФД",
            "ФП",
            "Дата покупки",
            "Сумма, руб.",
            "Статус",
            "Причина отказа",
            "Дата регистрации",
        ]
    )
    for receipt in queryset.select_related("user"):
        writer.writerow(
            [
                receipt.user.username,
                receipt.fn,
                receipt.fd,
                receipt.fp,
                receipt.purchased_at.strftime("%d.%m.%Y %H:%M"),
                f"{receipt.amount:.2f}".replace(".", ","),
                receipt.get_status_display(),
                receipt.rejection_reason,
                receipt.created_at.strftime("%d.%m.%Y %H:%M"),
            ]
        )
    return response


@admin.register(Receipt)
class ReceiptAdmin(admin.ModelAdmin):
    form = ReceiptAdminForm
    list_display = (
        "id",
        "user",
        "fn",
        "fd",
        "fp",
        "purchased_at",
        "amount",
        "status",
        "created_at",
    )
    list_filter = ("status", "purchased_at", "created_at")
    search_fields = ("fn", "fd", "fp", "user__username", "user__email")
    list_select_related = ("user",)
    readonly_fields = ("created_at", "photo_preview")
    actions = [export_accepted_csv]
    fieldsets = (
        (None, {"fields": ("user", "fn", "fd", "fp", "purchased_at", "amount")}),
        ("Проверка", {"fields": ("status", "rejection_reason")}),
        ("Фото чека", {"fields": ("photo", "photo_preview")}),
        ("Служебное", {"fields": ("created_at",)}),
    )

    @admin.display(description="Превью фото")
    def photo_preview(self, obj):
        if obj.photo:
            return format_html('<img src="{}" style="max-height:120px">', obj.photo.url)
        return "—"