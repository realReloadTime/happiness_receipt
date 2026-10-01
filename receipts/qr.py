"""Парсинг строки из QR-кода фискального чека (формат ФНС).

Пример строки из чека:
    t=20260612T1432&s=1890.00&fn=9288000100112345&i=1234&fp=3613054613&n=1

- t — дата и время покупки (YYYYMMDDTHHMM)
- s — сумма в рублях
- fn — фискальный номер (16 цифр)
- i — номер фискального документа (ФД)
- fp — фискальный признак (ФП)
"""
import re
from datetime import datetime

DATETIME_RE = re.compile(r"^\d{8}T\d{4}$")


class QRParsingError(ValueError):
    """Ошибка разбора строки из QR-кода с человекочитаемым описанием."""


def parse_qr_line(line: str) -> dict:
    """Разбирает строку из QR-кода и возвращает dict с ключами:
    fn, fd, fp, purchased_at (naive datetime), amount (float).

    При любой ошибке поднимает QRParsingError с описанием проблемы.
    """
    if not line or not line.strip():
        raise QRParsingError("Строка из QR-кода пуста.")

    params: dict[str, str] = {}
    for part in line.strip().split("&"):
        if "=" in part:
            key, value = part.split("=", 1)
            params[key.strip()] = value.strip()

    fn = params.get("fn", "")
    fd = params.get("i", "")
    fp = params.get("fp", "")
    s = params.get("s", "")
    t = params.get("t", "")

    errors: list[str] = []
    if not re.fullmatch(r"\d{16}", fn):
        errors.append("ФН (fn) — ожидается ровно 16 цифр")
    if not re.fullmatch(r"\d{1,10}", fd):
        errors.append("ФД (i) — ожидаются цифры (до 10)")
    if not re.fullmatch(r"\d{1,10}", fp):
        errors.append("ФП (fp) — ожидаются цифры (до 10)")

    try:
        amount = round(float(s), 2)
    except ValueError:
        amount = None
        errors.append("Сумма (s) не распознана как число")

    purchased_at = None
    if DATETIME_RE.fullmatch(t):
        try:
            purchased_at = datetime.strptime(t, "%Y%m%dT%H%M")
        except ValueError:
            errors.append("Дата (t) некорректна")
    else:
        errors.append("Дата (t) — ожидается формат YYYYMMDDTHHMM")

    if errors:
        raise QRParsingError("; ".join(errors))

    return {
        "fn": fn,
        "fd": fd,
        "fp": fp,
        "amount": amount,
        "purchased_at": purchased_at,
    }