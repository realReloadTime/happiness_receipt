import csv
import io

from django import forms
from django.contrib import admin, messages
from django.http import StreamingHttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
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


@admin.action(description="Принять выбранные чеки")
def accept_selected(modeladmin, request, queryset):
    """Быстрое подтверждение выбранных чеков («на проверке» → «принят»)."""
    updated = queryset.filter(status=Receipt.Status.PENDING).update(
        status=Receipt.Status.ACCEPTED, rejection_reason=""
    )
    messages.success(request, f"Принято чеков: {updated}.")


@admin.action(description="Отклонить выбранные чеки (с причиной)")
def reject_selected(modeladmin, request, queryset):
    """Отклонение выбранных чеков: сначала запрашиваем причину, затем применяем."""
    if "apply" in request.POST:
        reason = request.POST.get("rejection_reason", "").strip()
        if not reason:
            messages.error(request, "Укажите причину отказа.")
            return redirect(request.get_full_path())
        updated = queryset.filter(status=Receipt.Status.PENDING).update(
            status=Receipt.Status.REJECTED, rejection_reason=reason
        )
        messages.success(request, f"Отклонено чеков: {updated}.")
        return redirect(request.get_full_path())

    return TemplateResponse(
        request,
        "admin/receipts/receipt/reject_reason.html",
        {"receipts": queryset.select_related("user"), "action": "reject_selected"},
    )


class _Echo:
    """Псевдофайл для csv.writer, чтобы отдавать CSV потоком."""

    def write(self, value):
        return value


def _csv_rows(queryset):
    """Генератор строк CSV: BOM, заголовок и по одной строке на чек.

    Буфер StringIO переиспользуется для каждой строки (seek/truncate),
    поэтому память не растёт с размером выгрузки, а сам факт записи
    не зависит от возвращаемого значения csv.writer.writerow().
    """
    yield "\ufeff"  # BOM для корректного открытия в Excel
    buffer = io.StringIO()
    writer = csv.writer(buffer)
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
    yield buffer.getvalue()
    for receipt in queryset.select_related("user"):
        buffer.seek(0)
        buffer.truncate(0)
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
        yield buffer.getvalue()


@admin.action(description="Выгрузить принятые чеки в CSV")
def export_accepted_csv(modeladmin, request, queryset):
    """Потоковая выгрузка принятых чеков в CSV (BOM для Excel, без буферизации)."""
    queryset = queryset.filter(status=Receipt.Status.ACCEPTED)
    response = StreamingHttpResponse(
        _csv_rows(queryset), content_type="text/csv; charset=utf-8"
    )
    response["Content-Disposition"] = 'attachment; filename="accepted_receipts.csv"'
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
    actions = [accept_selected, reject_selected, export_accepted_csv]
    actions_on_top = True
    actions_on_bottom = True
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