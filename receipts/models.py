from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models

FN_VALIDATOR = RegexValidator(
    regex=r"^\d{16}$",
    message="ФН должен состоять ровно из 16 цифр",
    code="invalid_fn",
)
FD_VALIDATOR = RegexValidator(
    regex=r"^\d{1,10}$",
    message="ФД должен состоять из цифр (не более 10)",
    code="invalid_fd",
)
FP_VALIDATOR = RegexValidator(
    regex=r"^\d{1,10}$",
    message="ФП должен состоять из цифр (не более 10)",
    code="invalid_fp",
)


class Receipt(models.Model):
    """Чек, зарегистрированный пользователем в рамках промо-акции."""

    class Status(models.TextChoices):
        PENDING = "pending", "На проверке"
        ACCEPTED = "accepted", "Принят"
        REJECTED = "rejected", "Отклонён"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="receipts",
        verbose_name="Пользователь",
    )
    fn = models.CharField("ФН", max_length=16, validators=[FN_VALIDATOR], db_index=True)
    fd = models.CharField("Номер чека (ФД)", max_length=10, validators=[FD_VALIDATOR])
    fp = models.CharField("ФП", max_length=10, validators=[FP_VALIDATOR])
    purchased_at = models.DateTimeField("Дата покупки")
    amount = models.DecimalField("Сумма, ₽", max_digits=10, decimal_places=2)
    status = models.CharField(
        "Статус",
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    rejection_reason = models.TextField("Причина отказа", blank=True, default="")
    photo = models.ImageField(
        "Фото чека",
        upload_to="receipts/%Y/%m/",
        blank=True,
        null=True,
        help_text="Бонус: JPG/PNG/WebP до 10 МБ",
    )
    created_at = models.DateTimeField("Дата регистрации", auto_now_add=True)

    class Meta:
        # Второй ключ (-id) делает порядок детерминированным даже при
        # одинаковых created_at (быстрая массовая отправка чеков).
        ordering = ["-created_at", "-id"]
        verbose_name = "чек"
        verbose_name_plural = "чеки"
        constraints = [
            # Частичный уникальный индекс: один и тот же чек нельзя зарегистрировать
            # дважды, пока он «живой» (на проверке или принят). Отклонённый чек
            # можно подать заново — решение описано в README.
            models.UniqueConstraint(
                fields=["fn", "fd", "fp"],
                # Строковые значения статусов (см. Status выше): "pending", "accepted".
                condition=models.Q(status__in=["pending", "accepted"]),
                name="unique_active_receipt",
            )
        ]
        indexes = [
            # Кабинет и админка постоянно выбирают чеки по пользователю,
            # отсортированные по дате регистрации (от новых к старым).
            models.Index(fields=["user", "-created_at"], name="receipt_user_created_idx"),
        ]

    def __str__(self):
        return f"Чек {self.fn}/{self.fd}/{self.fp} — {self.get_status_display()}"