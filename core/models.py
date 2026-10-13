"""
Модель данных для анализа.
Ядро возвращает AnalysisResult, рендереры его отображают.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Level:
    """
    Один уровень (структурный или референсный).
    """

    price: float
    type: str
    weight: int
    tf_source: set = field(default_factory=set)
    confirmed: bool = False
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    label: str = ""
    tags: list[str] = field(default_factory=list)

    # --- Вычисляемые поля (заполняет analyzer) ---
    distance_atr: Optional[float] = None  # |price - current| / atr
    strength_score: Optional[float] = None  # weight × confirmed × tf_count × age_factor
    age_days: Optional[float] = None  # сколько дней с last_seen

    def to_dict(self) -> dict:
        d = asdict(self)
        d["price"] = round(self.price, 5)
        d["tf_source"] = sorted(self.tf_source)
        if self.distance_atr is not None:
            d["distance_atr"] = round(self.distance_atr, 2)
        if self.strength_score is not None:
            d["strength_score"] = round(self.strength_score, 1)
        if self.age_days is not None:
            d["age_days"] = round(self.age_days, 1)
        if self.first_seen:
            d["first_seen"] = self.first_seen.isoformat()
        if self.last_seen:
            d["last_seen"] = self.last_seen.isoformat()
        return d


@dataclass
class IndicatorSnapshot:
    """Снимок индикаторов на момент анализа."""

    ema_fast: Optional[float]
    ema_slow: Optional[float]
    rsi: Optional[float]
    adx: Optional[float]

    trend: str  # "up" / "down" / "none"
    adx_state: str  # "strong" / "trend" / "flat" / "none"
    rsi_state: str  # "overbought" / "oversold" / "near_overbought" / ...

    def to_dict(self) -> dict:
        d = asdict(self)
        # Округление индикаторов до 5 знаков — достаточно для цен CNYRUBF
        for key in ("ema_fast", "ema_slow", "rsi", "adx"):
            if d.get(key) is not None:
                d[key] = round(d[key], 5)
        return d


@dataclass
class Signal:
    """
    Торговый сигнал. Возвращается детектором signals.py.
    """

    direction: str  # "long" / "short"
    kind: str  # "bounce" / "breakout" / "trend_level"
    strength: str  # "weak" / "medium" / "strong"
    strength_score: float  # числовой score (1.0, 2.0, 3.0+)
    entry_price: float
    stop_price: float
    take_price: float
    matched_criteria: list[str] = field(default_factory=list)  # ["A1", "B1", ...]
    reasons: list[str] = field(default_factory=list)
    level_price: Optional[float] = None  # цена уровня, на котором сигнал

    def to_dict(self) -> dict:
        d = asdict(self)
        d["entry_price"] = round(self.entry_price, 5)
        d["stop_price"] = round(self.stop_price, 5)
        d["take_price"] = round(self.take_price, 5)
        d["strength_score"] = round(self.strength_score, 1)
        if self.level_price is not None:
            d["level_price"] = round(self.level_price, 5)
        return d


@dataclass
class AnalysisResult:
    """Полный результат анализа."""

    symbol: str
    timestamp: datetime
    current_price: float
    atr: float
    timeframe: str
    indicators: IndicatorSnapshot
    levels: list[Level]  # структурные (A+B)
    references: list[Level]  # референсные (C)
    signals: list[Signal] = field(default_factory=list)  # сигналы

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "current_price": round(self.current_price, 5),
            "atr": round(self.atr, 5),
            "timeframe": self.timeframe,
            "indicators": self.indicators.to_dict(),
            "levels": [lv.to_dict() for lv in self.levels],
            "references": [r.to_dict() for r in self.references],
            "signals": [s.to_dict() for s in self.signals],
        }
