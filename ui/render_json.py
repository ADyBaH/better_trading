# ui/render_json.py
"""JSON-рендерер AnalysisResult. Три формата: flat / nested / full."""

import json
from datetime import datetime

from core.models import AnalysisResult

import config


def _level_to_flat_dict(lv, is_reference: bool) -> dict:
    """Плоское представление уровня — общее для structural и reference."""
    d = {
        "price": lv.price,
        "type": lv.type,
        "weight": lv.weight,
        "label": lv.label,
        "tags": lv.tags,
        "source": "reference" if is_reference else "structural",
    }
    if not is_reference:
        d["tf_source"] = sorted(lv.tf_source)
        d["confirmed"] = lv.confirmed
        d["first_seen"] = lv.first_seen.isoformat() if lv.first_seen else None
        d["last_seen"] = lv.last_seen.isoformat() if lv.last_seen else None
    return d


def render_json(result: AnalysisResult, mode: str = "nested") -> str:
    """
    mode='flat'   — все уровни одним списком (structural + reference).
    mode='nested' — раздельно levels и references + indicators (default).
    mode='full'   — nested + метаданные (version, engine, debug).
    """
    if mode == "flat":
        payload = _build_flat(result)
    elif mode == "full":
        payload = _build_full(result)
    else:
        payload = _build_nested(result)

    return json.dumps(payload, ensure_ascii=False, indent=2)


def _build_flat(result: AnalysisResult) -> dict:
    """Все уровни в один список, отсортированный по цене (сверху вниз)."""
    all_levels = []
    for lv in result.levels:
        all_levels.append(_level_to_flat_dict(lv, is_reference=False))
    for r in result.references:
        all_levels.append(_level_to_flat_dict(r, is_reference=True))

    all_levels.sort(key=lambda d: d["price"], reverse=True)

    return {
        "symbol": result.symbol,
        "timestamp": result.timestamp.isoformat(),
        "current_price": result.current_price,
        "atr": result.atr,
        "levels": all_levels,
    }


def _build_nested(result: AnalysisResult) -> dict:
    """Раздельно structural и reference."""
    return {
        "symbol": result.symbol,
        "timestamp": result.timestamp.isoformat(),
        "timeframe": result.timeframe,
        "current_price": result.current_price,
        "atr": result.atr,
        "indicators": result.indicators.to_dict(),
        "levels": [lv.to_dict() for lv in result.levels],
        "references": [r.to_dict() for r in result.references],
    }


def _build_full(result: AnalysisResult) -> dict:
    """Nested + метаданные."""
    payload = _build_nested(result)
    payload["meta"] = {
        "version": config.__version__,
        "engine": config.ENGINE,
        "market": config.MARKET,
        "generated_at": datetime.now().isoformat(),
        "config": {
            "ema_fast": config.EMA_FAST,
            "ema_slow": config.EMA_SLOW,
            "rsi_period": config.RSI_PERIOD,
            "adx_period": config.ADX_PERIOD,
            "atr_period": config.ATR_PERIOD,
            "atr_tf": config.ATR_TF,
            "level_tolerance_atr": config.LEVEL_TOLERANCE_ATR,
            "level_range_atr": config.LEVELS_RANGE_ATR,
            "level_max_show": config.LEVELS_MAX_SHOW,
            "fractal_period": config.FRACTAL_PERIOD,
            "level_timeframes": config.LEVEL_TIMEFRAMES,
            "level_tf_weights": config.LEVEL_TF_WEIGHTS,
        },
    }
    return payload
