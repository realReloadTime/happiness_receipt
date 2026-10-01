from django.conf import settings

from .campaign import campaign_period_display, campaign_end, campaign_start, promo_zone


def campaign_period(request):
    """Добавляет в контекст всех шаблонов период акции из настроек (.env).

    Требование задания: «На странице выводите период из настроек».
    """
    start, end = campaign_period_display()
    fmt = "%Y-%m-%dT%H:%M"
    return {
        "campaign_start": start,
        "campaign_end": end,
        # ISO-представления границ для клиентской проверки дат в JS
        "campaign_start_iso": campaign_start().astimezone(promo_zone()).strftime(fmt),
        "campaign_end_iso": campaign_end().astimezone(promo_zone()).strftime(fmt),
        "photo_max_mb": settings.RECEIPT_PHOTO_MAX_MB,
    }