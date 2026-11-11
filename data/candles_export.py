"""
Сохранение свечей в JSON рядом с analysis_*.json.
Папка: storage/logs/YYYY-MM-DD/candles_<TF>_YYYY-MM-DD.json
"""

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from core.logger import get_logger
import config

log = get_logger(__name__)


def _candles_dir(dt: datetime) -> Path:
    """storage/logs/YYYY-MM-DD/ — та же папка, что у analysis_*.json."""
    base = Path(config.LOG_PATH).parent
    date_dir = base / dt.strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)
    return date_dir


def _candles_path(symbol: str, timeframe: str, dt: datetime) -> Path:
    date_str = dt.strftime("%Y-%m-%d")
    return _candles_dir(dt) / f"candles_{timeframe}_{date_str}.json"


def candles_to_list(df: pd.DataFrame, max_count: int | None = None) -> list[dict]:
    """DataFrame свечей → список dict (begin — ISO-строка)."""
    if df is None or df.empty:
        return []

    if max_count is not None:
        df = df.tail(max_count)

    out = []
    for _, row in df.iterrows():
        b = row["begin"]
        if hasattr(b, "isoformat"):
            b = b.isoformat()
        out.append(
            {
                "begin": b,
                "open": round(float(row["open"]), 5),
                "high": round(float(row["high"]), 5),
                "low": round(float(row["low"]), 5),
                "close": round(float(row["close"]), 5),
                "volume": int(row["volume"]) if pd.notna(row["volume"]) else 0,
            }
        )
    return out


def append_candles_snapshot(
    df: pd.DataFrame,
    symbol: str,
    timeframe: str,
    saved_at: datetime | None = None,
    has_signals: bool = False,
    signals_count: int = 0,
) -> Path | None:
    """
    Дописывает snapshot свечей в storage/logs/YYYY-MM-DD/candles_<TF>_YYYY-MM-DD.json.
    Обрезает до config.SAVE_CANDLES_MAX_SNAPSHOTS.
    Возвращает путь к файлу или None, если свечей нет.
    """
    if df is None or df.empty:
        return None

    saved_at = saved_at or datetime.now()
    path = _candles_path(symbol, timeframe, saved_at)

    candles = candles_to_list(df, max_count=config.SAVE_CANDLES_COUNT)

    # --- Читаем существующий файл ---
    data = None
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data.get("snapshots"), list):
                data["snapshots"] = []
        except (json.JSONDecodeError, KeyError):
            data = None

    if data is None:
        data = {
            "symbol": symbol,
            "timeframe": timeframe,
            "date": saved_at.strftime("%Y-%m-%d"),
            "snapshots": [],
        }

    # --- Добавляем snapshot ---
    data["snapshots"].append(
        {
            "saved_at": saved_at.isoformat(),
            "has_signals": has_signals,
            "signals_count": signals_count,
            "count": len(candles),
            "candles": candles,
        }
    )

    # --- Обрезаем ---
    if len(data["snapshots"]) > config.SAVE_CANDLES_MAX_SNAPSHOTS:
        data["snapshots"] = data["snapshots"][-config.SAVE_CANDLES_MAX_SNAPSHOTS :]

    data["count"] = len(data["snapshots"])
    data["last_updated"] = saved_at.isoformat()

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return path


def save_candles_snapshots(result, log=None) -> list[Path]:
    """
    Сохраняет снимки свечей для result в storage/logs/YYYY-MM-DD/
    (рядом с analysis_*.json).

    Управляется флагами config:
        SAVE_CANDLES              — глобальный выключатель (False → ничего не делаем);
        SAVE_CANDLES_ALWAYS       — True  → пишем КАЖДЫЙ цикл (вариант A);
                                    False → пишем только когда есть сигналы (вариант B);
        SAVE_CANDLES_MARK_SIGNALS — True  → в снимке ставим has_signals/signals_count
                                    (маркер «здесь был сигнал»);
        SAVE_CANDLES_TIMEFRAMES   — какие ТФ сохранять (например ["M15"]);
        SAVE_CANDLES_COUNT        — сколько свечей брать на снимок.

    result — AnalysisResult (нужны .symbol, .timestamp, .signals).

    Возвращает список путей к записанным файлам (может быть пустым).
    """
    _log = log or get_logger(__name__)

    # 0. Глобальный выключатель
    if not config.SAVE_CANDLES:
        return []

    has_signals = bool(result.signals)
    signals_count = len(result.signals)

    # 1. Режим: A (always) или B (on_signal)
    #    Если SAVE_CANDLES_ALWAYS=False и сигналов нет — писать нечего.
    if not config.SAVE_CANDLES_ALWAYS and not has_signals:
        _log.debug("candles: сигналов нет, SAVE_CANDLES_ALWAYS=False — пропуск")
        return []

    # 2. Маркер сигналов (B-часть). Если MARK_SIGNALS=False — не пишем маркер,
    #    даже если сигналы были (чистый режим A).
    if config.SAVE_CANDLES_MARK_SIGNALS:
        mark_has = has_signals
        mark_count = signals_count
    else:
        mark_has = False
        mark_count = 0

    # 3. Тянем свечи и пишем по каждому ТФ
    from data.api_facade import get_candles_tf

    paths: list[Path] = []

    for tf in config.SAVE_CANDLES_TIMEFRAMES:
        try:
            df_tf = get_candles_tf(tf, count=config.SAVE_CANDLES_COUNT)
        except Exception as e:
            _log.warning("candles: не удалось получить %s: %s", tf, e)
            continue

        if df_tf is None or df_tf.empty:
            _log.warning("candles: пустой DataFrame для %s — пропуск", tf)
            continue

        try:
            path = append_candles_snapshot(
                df_tf,
                symbol=result.symbol,
                timeframe=tf,
                saved_at=result.timestamp,
                has_signals=mark_has,
                signals_count=mark_count,
            )
        except Exception as e:
            _log.exception("candles: ошибка записи %s: %s", tf, e)
            continue

        if path is not None:
            paths.append(path)
            _log.info(
                "candles: %s → %s (signals=%d, has_signals=%s)",
                tf,
                path.name,
                mark_count,
                mark_has,
            )

    return paths
