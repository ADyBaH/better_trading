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

    Для структурных (A+B):
        - type: "up" / "down" / "mixed"
        - tf_source: {'H1', 'M15'}
        - confirmed: True, если на 2+ ТФ
        - first_seen / last_seen: время фракталов

    Для референсных (C):
        - type: "round" / "pdh" / "pdl" / "pwh" / "pwl"
        - tf_source: пустое множество
        - confirmed: False
        - first_seen / last_seen: None
        - label: "12.550" / "PDH" / "PWL" и т.п.
    """
    price: float
    type: str
    weight: int
    tf_source: set = field(default_factory=set)
    confirmed: bool = False
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    label: str = ""
    tags: list[str] = field(default_factory=list)   # ["+ round", "+ PDL"]

    def to_dict(self) -> dict:
        """Сериализация для JSON. set → list, datetime → isoformat."""
        d = asdict(self)
        d["tf_source"] = sorted(self.tf_source)
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

    trend: str          # "up" / "down" / "none"
    adx_state: str      # "strong" / "trend" / "flat"
    rsi_state: str      # "overbought" / "oversold" / "near_overbought" / ...

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AnalysisResult:
    """Полный результат анализа. Возвращается ядром, потребляется рендерерами."""
    symbol: str
    timestamp: datetime
    current_price: float
    atr: float
    timeframe: str                    # базовый ТФ анализа (M5)
    indicators: IndicatorSnapshot
    levels: list[Level]               # структурные (A+B)
    references: list[Level]           # референсные (C)

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "current_price": self.current_price,
            "atr": self.atr,
            "timeframe": self.timeframe,
            "indicators": self.indicators.to_dict(),
            "levels": [lv.to_dict() for lv in self.levels],
            "references": [r.to_dict() for r in self.references],
        }