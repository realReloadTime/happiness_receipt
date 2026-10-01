"""Период промо-акции: даты читаются из настроек (.env), а не зашиты в код.

Решение по часовым поясам (описано в README):
- границы акции задаются как календарные даты в часовом поясе акции PROMO_TIMEZONE;
- введённое пользователем время покупки трактуется как местное время акции
  и конвертируется в UTC для хранения и сравнения;
- часовой пояс покупателя на границы не влияет — у акции одна граница.
"""
from datetime import date, datetime, time as dt_time, timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

# Небольшой допуск на расхождение часов устройства пользователя,
# чтобы валидный чек не отклонялся из-за сдвига в несколько минут.
FUTURE_TOLERANCE = timedelta(minutes=5)


def promo_zone() -> ZoneInfo:
    return ZoneInfo(settings.PROMO_TIMEZONE)


def campaign_start() -> datetime:
    """Начало акции: 00:00:00 первого дня в часовом поясе акции (aware, UTC)."""
    start = date.fromisoformat(settings.PROMO_START_DATE)
    naive = datetime.combine(start, dt_time.min)
    return naive.replace(tzinfo=promo_zone()).astimezone(dt_timezone.utc)


def campaign_end() -> datetime:
    """Конец акции: конец последнего дня (23:59:59.999999) в часовом поясе акции."""
    end = date.fromisoformat(settings.PROMO_END_DATE)
    naive = datetime.combine(end, dt_time.max)
    return naive.replace(tzinfo=promo_zone()).astimezone(dt_timezone.utc)


def is_within_campaign(purchased_at: datetime) -> bool:
    """Попадает ли момент покупки в период акции (границы включительно)."""
    purchased_utc = purchased_at.astimezone(dt_timezone.utc)
    return campaign_start() <= purchased_utc <= campaign_end()


def is_in_future(purchased_at: datetime) -> bool:
    """Не в будущем ли момент покупки (с допуском FUTURE_TOLERANCE)."""
    purchased_utc = purchased_at.astimezone(dt_timezone.utc)
    return purchased_utc > timezone.now() + FUTURE_TOLERANCE


def make_aware_in_promo_tz(naive: datetime) -> datetime:
    """Интерпретируем наивное время, введённое пользователем, как время акции (UTC)."""
    return naive.replace(tzinfo=promo_zone()).astimezone(dt_timezone.utc)


def campaign_period_display() -> tuple[str, str]:
    """Человекочитаемые даты начала и конца акции для отображения на странице."""
    fmt = "%d.%m.%Y %H:%M"
    return (
        campaign_start().astimezone(promo_zone()).strftime(fmt),
        campaign_end().astimezone(promo_zone()).strftime(fmt),
    )