"""Реальные сделки (мок-режим по умолчанию)."""

from datetime import datetime
from core.logger import get_logger

import config
from data.api_alor_trade import place_order, cancel_order
from core.risk import calculate_position_size
from core.instruments import get_instrument

log = get_logger(__name__)

# Мок-режим: НЕ ставим реальные ордера
_MOCK_MODE = True

# Риск на сделку (рублей). 1% от 10000₽ = 100₽.
RISK_RUB_PER_TRADE = 100.0


def open_real_trade(signal) -> dict | None:
    """
    Открывает реальную сделку из сигнала.
    В мок-режиме — только логирует, ордер НЕ ставит.

    Возвращает:
        {
            "trade_id": str,
            "status": "mock" / "filled" / "rejected",
            "symbol": str,
            "direction": str,
            "entry_price": float,
            "stop_price": float,
            "take_price": float,
            "size": int,
            "order_id": str,
        }
    """
    inst = get_instrument(config.SYMBOL)

    # Размер позиции от риска
    size = calculate_position_size(
        risk_rub=RISK_RUB_PER_TRADE,
        entry_price=signal.entry_price,
        stop_price=signal.stop_price,
        step_cost=inst.step_cost,
        price_step=inst.price_step,
    )

    if size <= 0:
        log.warning("open_real_trade: size=0, пропуск")
        return None

    # Направление: long → buy, short → sell
    side = "buy" if signal.direction == "long" else "sell"

    # Ставим ордер (мок)
    order = place_order(
        symbol=config.SYMBOL,
        side=side,
        quantity=size,
        order_type="market",
    )

    trade_id = f"real-{datetime.now().timestamp()}"

    log.info(
        "REAL: %s %s %s %d @ %.3f (stop=%.3f, take=%.3f) → %s",
        trade_id,
        signal.direction,
        signal.kind,
        size,
        signal.entry_price,
        signal.stop_price,
        signal.take_price,
        order["status"],
    )

    return {
        "trade_id": trade_id,
        "status": order["status"],
        "symbol": config.SYMBOL,
        "direction": signal.direction,
        "entry_price": signal.entry_price,
        "stop_price": signal.stop_price,
        "take_price": signal.take_price,
        "size": size,
        "order_id": order["order_id"],
    }


def close_real_trade(trade_id: str, order_id: str | None = None) -> bool:
    """Закрывает реальную сделку. В мок-режиме — всегда True."""
    if _MOCK_MODE:
        log.info("MOCK: close real trade %s", trade_id)
        return True

    if order_id:
        return cancel_order(order_id)
    return False


def insert_real_trade(conn, real_trade: dict) -> int:
    """
    Записывает real-сделку в journal.db/trades.
    Возвращает id.
    """
    from trader.journal import Trade
    from trader import journal

    trade = Trade(
        symbol=real_trade["symbol"],
        direction=real_trade["direction"],
        entry_price=real_trade["entry_price"],
        datetime_open=datetime.now(),
        size=real_trade["size"],
        stop_price=real_trade["stop_price"],
        take_price=real_trade["take_price"],
        comment=f"real (mock) {real_trade['trade_id']}",
        signal_kind="real",
        signal_strength="mock",
        signal_score=0.0,
    )
    return journal.add_trade(trade)
