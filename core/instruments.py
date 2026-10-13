"""
Спецификации торговых инструментов.
Каждый инструмент — dataclass Instrument с параметрами контракта и комиссиями.
"""

from dataclasses import dataclass


@dataclass
class Instrument:
    """Спецификация одного торгового инструмента."""

    symbol: str  # "CNYRUBF"
    name: str  # человекочитаемое имя
    market: str  # "forts" / "shares" / "currency"
    engine: str  # "futures" / "stock" / "currency"
    price_step: float  # шаг цены (минимальное изменение)
    step_cost: float  # стоимость 1 шага в валюте расчёта
    lot_size: int  # размер контракта (в базовом активе)
    commission_exchange: float  # биржевой сбор за сделку (руб/контракт)
    commission_broker: float  # брокерская комиссия (руб/контракт)
    currency: str = "RUB"

    @property
    def commission_open(self) -> float:
        """Суммарная комиссия за открытие (биржа + брокер)."""
        return self.commission_exchange + self.commission_broker

    @property
    def commission_close(self) -> float:
        """Суммарная комиссия за закрытие (биржа + брокер)."""
        return self.commission_exchange + self.commission_broker

    @property
    def commission_round(self) -> float:
        """Суммарная комиссия за круг (открытие + закрытие)."""
        return self.commission_open + self.commission_close


INSTRUMENTS: dict[str, Instrument] = {
    "CNYRUBF": Instrument(
        symbol="CNYRUBF",
        name="Фьючерс на юань (вечный, MOEX)",
        market="forts",
        engine="futures",
        price_step=0.001,
        step_cost=1.0,
        lot_size=1000,
        commission_exchange=0.58,  # MOEX: сбор за регистрацию сделки
        commission_broker=0.45,  # Финам
        currency="RUB",
    ),
    # Позже: Si, RTS, BTCUSDT, EURRUBF, USDRUBF и т.д.
}


def get_instrument(symbol: str) -> Instrument:
    """Возвращает спецификацию инструмента. Бросает ValueError, если нет."""
    if symbol not in INSTRUMENTS:
        raise ValueError(
            f"Инструмент '{symbol}' не найден. "
            f"Доступные: {list(INSTRUMENTS.keys())}"
        )
    return INSTRUMENTS[symbol]


def list_instruments() -> list[str]:
    """Список доступных тикеров."""
    return list(INSTRUMENTS.keys())
