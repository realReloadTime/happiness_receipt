from django import template

from ..campaign import promo_zone

register = template.Library()


@register.filter
def promo_localtime(value):
    """Форматирует datetime в часовом поясе акции: ЧЧ:ММ ДД.ММ.ГГГГ (по макету)."""
    if value is None:
        return ""
    return value.astimezone(promo_zone()).strftime("%H:%M %d.%m.%Y")