"""Риск-менеджмент: расчёт размера позиции."""

from core.logger import get_logger

log = get_logger(__name__)


def calculate_position_size(
    risk_rub: float,
    entry_price: float,
    stop_price: float,
    step_cost: float,
    price_step: float,
    max_size: int = 10,
) -> int:
    """
    Считает размер позиции (контрактов) от риска.

    risk_rub — сколько рублей готов потерять (например, 1% депозита).
    entry_price, stop_price — цены входа и стопа.
    step_cost, price_step — из спецификации инструмента.
    max_size — максимум контрактов (защита от ошибки).

    Формула:
        stop_distance = |entry - stop|
        stop_points = stop_distance / price_step
        risk_per_contract = stop_points * step_cost
        size = risk_rub / risk_per_contract
    """
    if entry_price <= 0 or stop_price <= 0 or price_step <= 0 or step_cost <= 0:
        log.warning("calculate_position_size: некорректные параметры")
        return 0

    stop_distance = abs(entry_price - stop_price)
    if stop_distance == 0:
        log.warning("calculate_position_size: stop_distance = 0")
        return 0

    stop_points = stop_distance / price_step
    risk_per_contract = stop_points * step_cost
    if risk_per_contract <= 0:
        log.warning("calculate_position_size: risk_per_contract = 0")
        return 0

    size = int(risk_rub / risk_per_contract)
    size = max(1, min(size, max_size))  # минимум 1, максимум max_size

    log.info(
        "position_size: risk=%.2f₽, stop=%.1f pts, risk/contract=%.2f₽, size=%d",
        risk_rub,
        stop_points,
        risk_per_contract,
        size,
    )
    return size
