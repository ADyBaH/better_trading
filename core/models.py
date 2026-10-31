"""
Модель данных для анализа.
Ядро возвращает AnalysisResult, рендереры его отображают.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional


@dataclass
class Level:
    """Один уровень (структурный или референсный)."""

    price: float
    type: str
    weight: int
    tf_source: set = field(default_factory=set)
    confirmed: bool = False
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    label: str = ""
    tags: list[str] = field(default_factory=list)

    distance_atr: Optional[float] = None
    strength_score: Optional[float] = None
    age_days: Optional[float] = None

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

    trend: str  # up / down / strong_up / strong_down / transition / none
    adx_state: str  # strong / trend / flat / none
    rsi_state: str  # overbought / oversold / near_overbought / ...

    # --- НОВОЕ: контекст тренда ---
    day_trend: str = "unknown"  # bullish / bearish / neutral / unknown
    day_change_atr: float = 0.0
    structure: str = "mixed"  # bullish / bearish / mixed
    price_direction: str = "unknown"  # up / down / unknown
    vote_sum: int = 0
    vote_breakdown: dict = field(default_factory=dict)

    # --- Недельный тренд (новое) ---
    week_trend: str = "unknown"  # bullish / bearish / neutral / unknown
    week_change_atr: float = 0.0

    def to_dict(self) -> dict:
        d = asdict(self)
        for key in ("ema_fast", "ema_slow", "rsi", "adx"):
            if d.get(key) is not None:
                d[key] = round(d[key], 5)
        if d.get("day_change_atr") is not None:
            d["day_change_atr"] = round(d["day_change_atr"], 2)
        if d.get("week_change_atr") is not None:
            d["week_change_atr"] = round(d["week_change_atr"], 2)
        return d


@dataclass
class Signal:
    """
    Торговый сигнал.
    Обогащён context (снимок окружения), warnings (сомнения),
    risk_reward и net_rr (с учётом комиссии).
    """

    direction: str  # "long" / "short"
    kind: str  # "bounce" / "breakout" / "trend_level"
    strength: str  # "weak" / "medium" / "strong"
    strength_score: float
    entry_price: float
    stop_price: float
    take_price: float
    matched_criteria: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    level_price: Optional[float] = None

    # --- Обогащение (Шаг 1) ---
    risk_reward: Optional[float] = None  # gross R:R без комиссии
    net_rr: Optional[float] = None  # R:R с учётом комиссии
    warnings: list[str] = field(default_factory=list)
    context: dict = field(default_factory=dict)

    def compute_rr(self, commission_round: float = 0.0) -> None:
        """
        Считает risk_reward и net_rr.
        commission_round — комиссия за круг в тех же единицах, что entry/stop/take.
        """
        gross_risk = abs(self.entry_price - self.stop_price)
        gross_reward = abs(self.take_price - self.entry_price)

        if gross_risk > 0:
            self.risk_reward = round(gross_reward / gross_risk, 2)

        net_risk = gross_risk + commission_round
        net_reward = gross_reward - commission_round
        if net_risk > 0:
            self.net_rr = round(net_reward / net_risk, 2)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["entry_price"] = round(self.entry_price, 5)
        d["stop_price"] = round(self.stop_price, 5)
        d["take_price"] = round(self.take_price, 5)
        d["strength_score"] = round(self.strength_score, 2)
        if self.level_price is not None:
            d["level_price"] = round(self.level_price, 5)
        if self.risk_reward is not None:
            d["risk_reward"] = round(self.risk_reward, 2)
        if self.net_rr is not None:
            d["net_rr"] = round(self.net_rr, 2)
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
    levels: list[Level]
    references: list[Level]
    signals: list[Signal] = field(default_factory=list)
    order_book: dict = field(default_factory=dict)

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
            "order_book": self.order_book,
        }


def format_indicators(ind: "IndicatorSnapshot") -> str:
    """
    Человекочитаемая строка из IndicatorSnapshot.
    Использует новый trend (голосование), а не только EMA.
    """
    parts = []

    # --- Тренд (главный) ---
    trend_map = {
        "strong_up": "СИЛЬНЫЙ ВВЕРХ",
        "up": "ВВЕРХ",
        "down": "ВНИЗ",
        "strong_down": "СИЛЬНЫЙ ВНИЗ",
        "transition": "ПЕРЕХОД (transition)",
        "none": "нет данных",
    }
    trend_text = trend_map.get(ind.trend, ind.trend)
    parts.append(f"Тренд {trend_text} (голосов {ind.vote_sum:+d})")

    # --- ADX ---
    adx_map = {
        "strong": "сильный",
        "trend": "есть",
        "flat": "боковик",
        "none": "нет данных",
    }
    if ind.adx is not None:
        parts.append(f"ADX {ind.adx:.1f} ({adx_map.get(ind.adx_state, '')})")

    # --- RSI ---
    rsi_map = {
        "overbought": "перекупленность",
        "oversold": "перепроданность",
        "near_overbought": "близко к перекупленности",
        "near_oversold": "близко к перепроданности",
        "neutral": "нейтрально",
        "none": "нет данных",
    }
    if ind.rsi is not None:
        parts.append(f"RSI {ind.rsi:.1f} ({rsi_map.get(ind.rsi_state, '')})")

    return " | ".join(parts)


def format_trend_context(ind: "IndicatorSnapshot") -> str:
    """
    Дополнительная строка про контекст тренда:
    day_trend, structure, price_direction.
    """
    parts = []

    day_map = {
        "bullish": "бычий",
        "bearish": "медвежий",
        "neutral": "нейтральный",
        "unknown": "?",
    }
    parts.append(
        f"День: {day_map.get(ind.day_trend, ind.day_trend)} ({ind.day_change_atr:+.1f} ATR)"
    )

    struct_map = {"bullish": "HH/HL", "bearish": "LH/LL", "mixed": "mixed"}
    parts.append(f"Структура: {struct_map.get(ind.structure, ind.structure)}")

    price_map = {"up": "растёт", "down": "падает", "unknown": "?"}
    parts.append(f"Цена: {price_map.get(ind.price_direction, ind.price_direction)}")

    return " | ".join(parts)
