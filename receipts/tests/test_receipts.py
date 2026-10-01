"""Тесты: валидация чека, QR-парсер, API, кабинет, админка."""
import datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase, override_settings
from django.urls import reverse

from receipts.admin import ReceiptAdminForm
from receipts.campaign import make_aware_in_promo_tz
from receipts.forms import DUPLICATE_MESSAGE, ReceiptForm, RegistrationForm
from receipts.models import Receipt
from receipts.qr import QRParsingError, parse_qr_line

User = get_user_model()

# Период акции фиксируем явно, чтобы тесты не зависели от .env
CAMPAIGN = {
    "PROMO_START_DATE": "2026-10-01",
    "PROMO_END_DATE": "2026-10-31",
    "PROMO_TIMEZONE": "Asia/Novosibirsk",
}

# «Сейчас» внутри периода акции (для проверки «чека из будущего»)
FROZEN_NOW = datetime.datetime(2026, 10, 20, 12, 0, tzinfo=datetime.timezone.utc)
# «Сейчас» уже после окончания акции (для проверки границ периода)
AFTER_CAMPAIGN_NOW = datetime.datetime(2026, 11, 5, 12, 0, tzinfo=datetime.timezone.utc)

VALID = {"fn": "9288000100112345", "fd": "1234", "fp": "3613054613"}


def dt(year, month, day, hour=12, minute=0):
    return make_aware_in_promo_tz(datetime.datetime(year, month, day, hour, minute))


def form_data(**overrides):
    data = {
        "fn": VALID["fn"],
        "fd": VALID["fd"],
        "fp": VALID["fp"],
        "purchased_at": "2026-10-15T12:00",
        "amount": "1890.50",
        "qr_line": "",
    }
    data.update(overrides)
    return data


def patch_now(value=FROZEN_NOW):
    """Мок «текущего момента». ВАЖНО: вся валидация должна происходить ВНУТРИ
    контекста, иначе время вернётся к реальному (влияет на проверку будущего)."""
    return mock.patch("receipts.campaign.timezone.now", return_value=value)


class ReceiptValidationTests(TestCase):
    """Валидация формы чека."""

    @override_settings(**CAMPAIGN)
    def test_valid_form_creates_pending_receipt(self):
        with patch_now():
            form = ReceiptForm(data=form_data())
            self.assertTrue(form.is_valid(), form.errors)
        receipt = form.save(commit=False)
        receipt.user = User.objects.create_user("u1", password="pass")
        receipt.save()
        self.assertEqual(receipt.status, Receipt.Status.PENDING)

    @override_settings(**CAMPAIGN)
    def test_amount_below_minimum_rejected(self):
        with patch_now():
            form = ReceiptForm(data=form_data(amount="999.99"))
            self.assertFalse(form.is_valid())
            self.assertIn("amount", form.errors)

    @override_settings(**CAMPAIGN)
    def test_amount_exact_minimum_accepted(self):
        with patch_now():
            form = ReceiptForm(data=form_data(amount="1000"))
            self.assertTrue(form.is_valid(), form.errors)

    @override_settings(**CAMPAIGN)
    def test_purchase_before_campaign_rejected(self):
        with patch_now():
            form = ReceiptForm(data=form_data(purchased_at="2026-09-30T23:59"))
            self.assertFalse(form.is_valid())
            self.assertIn("purchased_at", form.errors)

    @override_settings(**CAMPAIGN)
    def test_purchase_after_campaign_rejected(self):
        with patch_now():
            form = ReceiptForm(data=form_data(purchased_at="2026-11-01T00:00"))
            self.assertFalse(form.is_valid())
            self.assertIn("purchased_at", form.errors)

    @override_settings(**CAMPAIGN)
    def test_boundaries_inclusive(self):
        # Границы: начало первого дня и конец последнего дня (время акции).
        with patch_now(AFTER_CAMPAIGN_NOW):
            start = ReceiptForm(data=form_data(purchased_at="2026-10-01T00:00"))
            self.assertTrue(start.is_valid(), start.errors)
            end = ReceiptForm(data=form_data(purchased_at="2026-10-31T23:59"))
            self.assertTrue(end.is_valid(), end.errors)

    @override_settings(**CAMPAIGN)
    def test_future_purchase_rejected(self):
        with patch_now():
            form = ReceiptForm(data=form_data(purchased_at="2026-10-21T12:00"))
            self.assertFalse(form.is_valid())
            self.assertIn("purchased_at", form.errors)

    @override_settings(**CAMPAIGN)
    def test_invalid_fn_rejected(self):
        with patch_now():
            form = ReceiptForm(data=form_data(fn="123"))
            self.assertFalse(form.is_valid())
            self.assertIn("fn", form.errors)

    @override_settings(**CAMPAIGN)
    def test_non_digit_fd_rejected(self):
        with patch_now():
            form = ReceiptForm(data=form_data(fd="abc"))
            self.assertFalse(form.is_valid())
            self.assertIn("fd", form.errors)

    @override_settings(**CAMPAIGN)
    def test_duplicate_pending_receipt_rejected_with_message(self):
        user = User.objects.create_user("u1", password="pass")
        Receipt.objects.create(user=user, purchased_at=dt(2026, 10, 15), amount="1500.00", **VALID)
        with patch_now():
            form = ReceiptForm(data=form_data())
            self.assertFalse(form.is_valid())
            self.assertIn(DUPLICATE_MESSAGE, str(form.non_field_errors()))

    @override_settings(**CAMPAIGN)
    def test_duplicate_accepted_receipt_rejected(self):
        user = User.objects.create_user("u1", password="pass")
        Receipt.objects.create(
            user=user, purchased_at=dt(2026, 10, 15), amount="1500.00",
            status=Receipt.Status.ACCEPTED, **VALID
        )
        with patch_now():
            form = ReceiptForm(data=form_data())
            self.assertFalse(form.is_valid())
            self.assertIn(DUPLICATE_MESSAGE, str(form.non_field_errors()))

    @override_settings(**CAMPAIGN)
    def test_resubmit_rejected_receipt_allowed(self):
        user = User.objects.create_user("u1", password="pass")
        Receipt.objects.create(
            user=user, purchased_at=dt(2026, 10, 15), amount="1500.00",
            status=Receipt.Status.REJECTED, rejection_reason="Не видно чека", **VALID
        )
        with patch_now():
            form = ReceiptForm(data=form_data())
            self.assertTrue(form.is_valid(), form.errors)

    @override_settings(**CAMPAIGN)
    def test_db_constraint_blocks_duplicate_even_for_other_user(self):
        """Частичный уникальный индекс блокирует дубликат на уровне БД."""
        user1 = User.objects.create_user("u1", password="pass")
        user2 = User.objects.create_user("u2", password="pass")
        Receipt.objects.create(user=user1, purchased_at=dt(2026, 10, 15), amount="1500.00", **VALID)
        with self.assertRaises(IntegrityError):
            Receipt.objects.create(
                user=user2, purchased_at=dt(2026, 10, 16), amount="1500.00", **VALID
            )

    @override_settings(**CAMPAIGN)
    def test_qr_line_autofills_form(self):
        with patch_now():
            form = ReceiptForm(
                data={
                    "qr_line": (
                        "t=20261015T1200&s=1890.00&fn=9288000100112345&i=1234"
                        "&fp=3613054613&n=1"
                    ),
                    "fn": "",
                    "fd": "",
                    "fp": "",
                    "purchased_at": "",
                    "amount": "",
                }
            )
            self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["fn"], VALID["fn"])
        self.assertEqual(form.cleaned_data["fd"], "1234")
        self.assertEqual(form.cleaned_data["fp"], "3613054613")
        self.assertEqual(form.cleaned_data["amount"], Decimal("1890.00"))
        self.assertEqual(form.cleaned_data["purchased_at"], dt(2026, 10, 15, 12, 0))

    @override_settings(**CAMPAIGN)
    def test_bad_qr_line_shows_error(self):
        with patch_now():
            form = ReceiptForm(data=form_data(qr_line="это не QR-строка"))
            self.assertFalse(form.is_valid())
            self.assertIn("qr_line", form.errors)


class QRParserTests(TestCase):
    def test_parse_valid_line(self):
        line = "t=20260612T1432&s=1890.00&fn=9288000100112345&i=1234&fp=3613054613&n=1"
        parsed = parse_qr_line(line)
        self.assertEqual(parsed["fn"], "9288000100112345")
        self.assertEqual(parsed["fd"], "1234")
        self.assertEqual(parsed["fp"], "3613054613")
        self.assertEqual(parsed["amount"], 1890.0)
        self.assertEqual(parsed["purchased_at"], datetime.datetime(2026, 6, 12, 14, 32))

    def test_parse_missing_params_raises(self):
        with self.assertRaises(QRParsingError):
            parse_qr_line("fn=9288000100112345")

    def test_parse_garbage_raises(self):
        with self.assertRaises(QRParsingError):
            parse_qr_line("qwe=asd&foo=bar")

    def test_parse_empty_raises(self):
        with self.assertRaises(QRParsingError):
            parse_qr_line("   ")


class ReceiptPageAndApiTests(TestCase):
    _counter = 1000

    @override_settings(**CAMPAIGN)
    def setUp(self):
        self.user = User.objects.create_user("buyer", password="pass")
        self.other = User.objects.create_user("other", password="pass")

    def make(self, user, **kwargs):
        """Создаёт чек с уникальными реквизитами (связка ФН+ФД+ФП глобально уникальна)."""
        type(self)._counter += 1
        n = type(self)._counter
        data = dict(fn="9288000100%08d" % n, fd=str(n), fp=str(n + 5000))
        data.update(kwargs)
        return Receipt.objects.create(
            user=user, purchased_at=dt(2026, 10, 15), amount="1500.00", **data
        )

    def test_cabinet_requires_login(self):
        response = self.client.get(reverse("receipts:cabinet"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_register_requires_login(self):
        response = self.client.get(reverse("receipts:register_receipt"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    @override_settings(**CAMPAIGN)
    def test_cabinet_paginates_by_10_newest_first(self):
        for i in range(12):
            self.make(self.user, fn="928800010011%04d" % (1000 + i), fd=str(i), fp=str(i))
        self.client.force_login(self.user)

        page1 = self.client.get(reverse("receipts:cabinet"))
        self.assertEqual(page1.status_code, 200)
        page1_ids = [r.id for r in page1.context["page_obj"].object_list]
        self.assertEqual(len(page1_ids), 10)
        # Порядок: от новых к старым (created_at + id — детерминировано)
        self.assertEqual(page1_ids, sorted(page1_ids, reverse=True))

        page2 = self.client.get(reverse("receipts:cabinet") + "?page=2")
        self.assertEqual(len(page2.context["page_obj"].object_list), 2)

    def test_api_requires_auth(self):
        response = self.client.get(reverse("receipts:api_receipts"))
        self.assertEqual(response.status_code, 403)

    @override_settings(**CAMPAIGN)
    def test_api_returns_only_own_receipts(self):
        self.make(self.user)
        self.make(self.other)
        self.client.force_login(self.user)
        response = self.client.get(reverse("receipts:api_receipts"))
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["count"], 1)
        ids = {item["id"] for item in data["results"]}
        self.assertEqual(ids, {r.id for r in Receipt.objects.filter(user=self.user)})

    @override_settings(**CAMPAIGN)
    def test_api_does_not_leak_foreign_receipts_with_any_params(self):
        my_receipt = self.make(self.user)
        other_receipt = self.make(self.other)
        self.client.force_login(self.user)
        params = [
            "?id=%d" % other_receipt.id,
            "?user_id=%d" % self.other.id,
            "?user=%d" % self.other.id,
            "?fn=%s" % other_receipt.fn,
            "?status=accepted",
        ]
        for query in params:
            response = self.client.get(reverse("receipts:api_receipts") + query)
            data = response.json()
            ids = [item["id"] for item in data["results"]]
            self.assertNotIn(other_receipt.id, ids)
            self.assertIn(my_receipt.id, ids)

    @override_settings(**CAMPAIGN)
    def test_ajax_register_success_returns_json(self):
        with patch_now():
            self.client.force_login(self.user)
            response = self.client.post(
                reverse("receipts:register_receipt"),
                data=form_data(),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(
            response.status_code, 200,
            "status=%s location=%s" % (response.status_code, response.get("Location")),
        )
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(Receipt.objects.filter(user=self.user).count(), 1)

    @override_settings(**CAMPAIGN)
    def test_ajax_register_returns_field_errors_as_json(self):
        with patch_now():
            self.client.force_login(self.user)
            response = self.client.post(
                reverse("receipts:register_receipt"),
                data=form_data(amount="10"),
                HTTP_X_REQUESTED_WITH="XMLHttpRequest",
            )
        self.assertEqual(
            response.status_code, 400,
            "status=%s location=%s" % (response.status_code, response.get("Location")),
        )
        payload = response.json()
        self.assertFalse(payload["ok"])
        self.assertIn("amount", payload["errors"])
        self.assertEqual(Receipt.objects.count(), 0)


class RegistrationTests(TestCase):
    """Регистрация участника: обязательный корректный и уникальный e-mail."""

    def data(self, **overrides):
        payload = {
            "username": "newuser",
            "email": "user@example.com",
            "password1": "secret-pass-123",
            "password2": "secret-pass-123",
        }
        payload.update(overrides)
        return payload

    def test_registration_rejects_bad_email(self):
        form = RegistrationForm(data=self.data(email="not-an-email"))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_registration_rejects_duplicate_email_case_insensitive(self):
        User.objects.create_user("existing", email="same@example.com", password="pass")
        form = RegistrationForm(data=self.data(email="SAME@example.com"))
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_registration_success_saves_lowercased_email(self):
        form = RegistrationForm(data=self.data(email="User@Example.COM"))
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.email, "user@example.com")

    def test_signup_page_renders_email_field(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'type="email"')


class AdminTests(TestCase):
    @override_settings(**CAMPAIGN)
    def setUp(self):
        self.moderator = User.objects.create_superuser("mod", email="m@example.com", password="pass")
        self.buyer = User.objects.create_user("buyer", password="pass")

    @override_settings(**CAMPAIGN)
    def test_rejection_requires_reason(self):
        form = ReceiptAdminForm(
            data={
                "user": self.buyer.id,
                "fn": VALID["fn"],
                "fd": "1234",
                "fp": "3613054613",
                "purchased_at": "2026-10-15 12:00",
                "amount": "1500.00",
                "status": Receipt.Status.REJECTED,
                "rejection_reason": "",
            }
        )
        self.assertFalse(form.is_valid())
        self.assertIn("rejection_reason", form.errors)

    @override_settings(**CAMPAIGN)
    def test_reason_cleared_when_not_rejected(self):
        form = ReceiptAdminForm(
            data={
                "user": self.buyer.id,
                "fn": VALID["fn"],
                "fd": "1234",
                "fp": "3613054613",
                "purchased_at": "2026-10-15 12:00",
                "amount": "1500.00",
                "status": Receipt.Status.ACCEPTED,
                "rejection_reason": "Старая причина",
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data["rejection_reason"], "")

    @override_settings(**CAMPAIGN)
    def test_csv_export_contains_only_accepted(self):
        accepted = Receipt.objects.create(
            user=self.buyer, purchased_at=dt(2026, 10, 15), amount="1500.00",
            status=Receipt.Status.ACCEPTED, fn="9288000100110001", fd="1", fp="11",
        )
        pending = Receipt.objects.create(
            user=self.buyer, purchased_at=dt(2026, 10, 16), amount="1200.00",
            fn="9288000100110002", fd="2", fp="22",
        )
        self.client.force_login(self.moderator)
        response = self.client.post(
            reverse("admin:receipts_receipt_changelist"),
            {"action": "export_accepted_csv", "_selected_action": [accepted.pk, pending.pk]},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8-sig")
        self.assertIn("9288000100110001", content)
        self.assertNotIn("9288000100110002", content)