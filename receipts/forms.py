import decimal

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.http import QueryDict
from django.utils import timezone

from .campaign import (
    campaign_end_iso,
    campaign_period_display,
    campaign_start_iso,
    is_in_future,
    is_within_campaign,
    make_aware_in_promo_tz,
)
from .models import Receipt
from .qr import QRParsingError, parse_qr_line

DUPLICATE_EMAIL_MESSAGE = "Пользователь с такой почтой уже зарегистрирован."


class RegistrationForm(UserCreationForm):
    """Регистрация участника акции: обязательный корректный и уникальный e-mail."""

    email = forms.EmailField(
        label="Электронная почта",
        required=True,
        widget=forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "name@example.com"}),
        error_messages={"invalid": "Введите корректный e-mail."},
    )

    class Meta:
        model = get_user_model()
        fields = ("username", "email")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(DUPLICATE_EMAIL_MESSAGE)
        return email

DUPLICATE_MESSAGE = (
    "Этот чек уже зарегистрирован. Повторная регистрация того же чека невозможна."
)
MIN_AMOUNT = decimal.Decimal("1000.00")


class ReceiptForm(forms.ModelForm):
    """Форма регистрации чека с серверной валидацией."""

    qr_line = forms.CharField(
        label="Вставить строку из QR-кода",
        required=False,
        widget=forms.TextInput(
            attrs={
                "placeholder": "t=20260612T1432&s=1890.00&fn=...&i=...&fp=...",
                "autocomplete": "off",
                "data-qr": "true",
            }
        ),
        help_text="Бонус: вставьте строку из QR-кода чека — реквизиты заполнятся автоматически.",
    )
    purchased_at = forms.DateTimeField(
        label="Дата и время покупки",
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M"],
        widget=forms.DateTimeInput(
            attrs={"type": "datetime-local"}, format="%Y-%m-%dT%H:%M"
        ),
    )
    amount = forms.DecimalField(
        label="Сумма, ₽",
        min_value=MIN_AMOUNT,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01", "min": "1000"}),
        error_messages={
            "min_value": "Минимальная сумма чека — 1000 ₽.",
            "invalid": "Введите корректную сумму (например, 1890.50).",
        },
    )

    class Meta:
        model = Receipt
        fields = ["fn", "fd", "fp", "purchased_at", "amount", "photo"]
        widgets = {
            "fn": forms.TextInput(
                attrs={
                    "placeholder": "16 цифр",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                    "maxlength": "16",
                }
            ),
            "fd": forms.TextInput(
                attrs={
                    "placeholder": "до 10 цифр",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                    "maxlength": "10",
                }
            ),
            "fp": forms.TextInput(
                attrs={
                    "placeholder": "до 10 цифр",
                    "inputmode": "numeric",
                    "autocomplete": "off",
                    "maxlength": "10",
                }
            ),
            "photo": forms.FileInput(attrs={"accept": "image/jpeg,image/png,image/webp"}),
        }
        error_messages = {
            "fn": {"invalid": "ФН должен состоять ровно из 16 цифр."},
            "fd": {"invalid": "ФД должен состоять из цифр (не более 10)."},
            "fp": {"invalid": "ФП должен состоять из цифр (не более 10)."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Границы выбора даты в браузере: период акции из настроек.
        self.fields["purchased_at"].widget.attrs["min"] = campaign_start_iso()
        self.fields["purchased_at"].widget.attrs["max"] = campaign_end_iso()
        # Бонус: если пользователь вставил строку из QR-кода, заполняем
        # недостающие поля ДО валидации полей (иначе появятся ошибки «заполните поле»).
        if self.is_bound:
            qr_line = (self.data.get("qr_line") or "").strip()
            if qr_line:
                self._apply_qr_autofill(qr_line)

    def _apply_qr_autofill(self, qr_line: str) -> None:
        """Подставляет реквизиты из QR-строки в data формы (не перезаписывая ручной ввод)."""
        try:
            parsed = parse_qr_line(qr_line)
        except QRParsingError:
            return  # сообщение об ошибке добавим в clean()

        data = QueryDict(mutable=True)
        data.update(self.data)
        for key, value in parsed.items():
            field_name = key  # fn, fd, fp, amount, purchased_at — совпадают с именами полей
            if data.get(field_name):
                continue  # пользователь уже ввёл значение вручную
            if field_name == "purchased_at":
                data[field_name] = value.strftime("%Y-%m-%dT%H:%M")
            elif field_name == "amount":
                data[field_name] = format(value, ".2f")
            else:
                data[field_name] = value
        self.data = data

    def clean_purchased_at(self):
        purchased_at = self.cleaned_data.get("purchased_at")
        if purchased_at is not None:
            # Django уже интерпретировал наивный ввод пользователя как текущий
            # часовой пояс (UTC). Достаём «настенные часы» ввода и трактуем их
            # как время акции — часовой пояс покупателя на границы не влияет.
            current_tz = timezone.get_current_timezone()
            wall_clock = purchased_at.astimezone(current_tz).replace(tzinfo=None)
            purchased_at = make_aware_in_promo_tz(wall_clock)
        return purchased_at

    def clean_photo(self):
        photo = self.cleaned_data.get("photo")
        if photo:
            from django.conf import settings

            max_bytes = int(settings.RECEIPT_PHOTO_MAX_MB * 1024 * 1024)
            if photo.size > max_bytes:
                raise forms.ValidationError(
                    f"Файл слишком большой. Максимальный размер — {settings.RECEIPT_PHOTO_MAX_MB:g} МБ."
                )
            if not photo.content_type.startswith("image/"):
                raise forms.ValidationError("Загрузите файл изображения (JPG, PNG или WebP).")
        return photo

    def clean(self):
        cleaned = super().clean()

        # --- Проверка строки QR-кода (если автозаполнение не сработало) ----------
        qr_line = cleaned.get("qr_line")
        if qr_line:
            try:
                parse_qr_line(qr_line)
            except QRParsingError as exc:
                self.add_error("qr_line", str(exc))

        fn = cleaned.get("fn")
        fd = cleaned.get("fd")
        fp = cleaned.get("fp")
        purchased_at = cleaned.get("purchased_at")

        # --- Период акции и «чек из будущего» --------------------------------------
        if purchased_at is not None:
            if not is_within_campaign(purchased_at):
                start, end = campaign_period_display()
                self.add_error(
                    "purchased_at",
                    f"Покупка должна быть совершена в период акции: с {start} по {end} (время акции).",
                )
            if is_in_future(purchased_at):
                self.add_error("purchased_at", "Дата покупки не может быть в будущем.")

        # --- Уникальность ФН + ФД + ФП ---------------------------------------------
        # Отклонённые чеки можно подать заново; «живые» (на проверке/принятые)
        # дублировать нельзя. На уровне БД это же гарантирует частичный
        # уникальный индекс (защита от гонки).
        if fn and fd and fp and not self.errors:
            duplicates = Receipt.objects.filter(fn=fn, fd=fd, fp=fp).exclude(
                status=Receipt.Status.REJECTED
            )
            if self.instance.pk:
                duplicates = duplicates.exclude(pk=self.instance.pk)
            if duplicates.exists():
                self.add_error(None, DUPLICATE_MESSAGE)

        return cleaned