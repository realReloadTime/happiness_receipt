"""Розыгрыш призов.

После окончания акции выбирает победителей случайным образом из ПРИНЯТЫХ
чеков (по одному призу на пользователя — берётся последний принятый чек).
Количество победителей задаётся в .env: PROMO_WINNERS_COUNT.

Команда идемпотентна: если розыгрыш уже проводился (есть чеки со статусами
won/lost), повторный запуск ничего не меняет. Вызывается автоматически
при старте контейнера (entrypoint.sh), в проде можно повесить на cron/beat.
"""
import random

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from receipts.campaign import campaign_end
from receipts.models import Receipt


class Command(BaseCommand):
    help = "Выбирает победителей из принятых чеков после окончания акции."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Провести розыгрыш, даже если акция ещё не закончилась (для отладки).",
        )

    def handle(self, *args, **options):
        now = timezone.now()
        if now < campaign_end() and not options["force"]:
            self.stdout.write("Акция ещё не закончилась — розыгрыш пропущен.")
            return

        if Receipt.objects.filter(
            status__in=[Receipt.Status.WON, Receipt.Status.LOST]
        ).exists():
            self.stdout.write("Розыгрыш уже проведён — повторный пропущен.")
            return

        accepted = list(
            Receipt.objects.filter(status=Receipt.Status.ACCEPTED).order_by(
                "user_id", "-purchased_at"
            )
        )
        if not accepted:
            self.stdout.write("Нет принятых чеков для розыгрыша.")
            return

        # Один участник — один приз: за каждого пользователя берём последний принятый чек
        user_best: dict[int, Receipt] = {}
        for receipt in accepted:
            user_best.setdefault(receipt.user_id, receipt)
        candidates = list(user_best.values())

        winners_count = min(
            int(getattr(settings, "PROMO_WINNERS_COUNT", 3)), len(candidates)
        )
        winner_pks = {r.pk for r in random.sample(candidates, winners_count)}

        for receipt in accepted:
            receipt.status = (
                Receipt.Status.WON if receipt.pk in winner_pks else Receipt.Status.LOST
            )
        Receipt.objects.bulk_update(accepted, ["status"])

        self.stdout.write(self.style.SUCCESS(f"Победителей выбрано: {winners_count}."))