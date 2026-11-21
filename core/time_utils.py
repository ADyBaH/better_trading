"""Утилиты времени: МСК, partial_day."""

from datetime import datetime, timedelta, timezone


def now_msk() -> datetime:
    """
    Текущее время в МСК (UTC+3), naive (без tzinfo).

    Naive — потому что весь проект работает с naive datetime
    (ALOR отдаёт naive МСК, `created_at` в paper_trades — naive).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=3)


def is_partial_day(
    now: datetime | None = None,
    day_close_hour: int = 18,
) -> bool:
    """
    True, если день не завершён (now < day_close_hour МСК).

    now — точка отсчёта (naive, МСК). По умолчанию — now_msk().
    day_close_hour — час закрытия (по умолчанию 18:00 МСК).
    """
    now = now or now_msk()
    return now.hour < day_close_hour
