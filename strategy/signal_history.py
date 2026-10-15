"""
История сигналов. Сохраняется в data/signals_history.json.
Нужна для cooldown-проверки (был ли противоположный сигнал недавно).
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

from core.logger import get_logger
from core.models import Signal

import config

log = get_logger(__name__)


HISTORY_FILE = Path(config.DB_PATH).parent / "signals_history.json"
MAX_ENTRIES = 100  # храним последние 100 сигналов


def _load_history() -> list[dict]:
    """Читает историю сигналов. Если файла нет — возвращает []."""
    if not HISTORY_FILE.exists():
        return []
    try:
        with HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return []
    except Exception as e:
        log.warning("Не удалось прочитать %s: %s", HISTORY_FILE, e)
        return []


def _save_history(entries: list[dict]) -> None:
    """Сохраняет историю, обрезая до MAX_ENTRIES."""
    entries = entries[-MAX_ENTRIES:]
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=2)


def append_signals(signals: list[Signal], symbol: str) -> None:
    """Дописывает новые сигналы в историю."""
    if not signals:
        return

    history = _load_history()
    now = datetime.now()

    for s in signals:
        history.append(
            {
                "timestamp": now.isoformat(),
                "symbol": symbol,
                "direction": s.direction,
                "kind": s.kind,
                "strength": s.strength,
                "strength_score": s.strength_score,
                "entry_price": s.entry_price,
                "stop_price": s.stop_price,
                "take_price": s.take_price,
                "level_price": s.level_price,
                "risk_reward": s.risk_reward,
                "net_rr": s.net_rr,
                "matched_criteria": s.matched_criteria,
                "warnings": s.warnings,
                "context": s.context,
            }
        )

    _save_history(history)
    log.info("Записано в историю сигналов: %d (всего %d)", len(signals), len(history))


def get_recent_signal(
    symbol: str,
    lookback_minutes: int = 120,
) -> dict | None:
    """
    Возвращает последний сигнал за последние `lookback_minutes` минут.
    Если ничего не найдено — None.
    """
    history = _load_history()
    cutoff = datetime.now() - timedelta(minutes=lookback_minutes)

    candidates = []
    for entry in history:
        if entry.get("symbol") != symbol:
            continue
        try:
            ts = datetime.fromisoformat(entry["timestamp"])
        except Exception:
            continue
        if ts >= cutoff:
            candidates.append((ts, entry))

    if not candidates:
        return None

    # Самый свежий
    candidates.sort(key=lambda x: x[0], reverse=True)
    ts, entry = candidates[0]

    age_min = int((datetime.now() - ts).total_seconds() / 60)
    return {
        "direction": entry.get("direction"),
        "kind": entry.get("kind"),
        "age_min": age_min,
        "timestamp": ts,
    }
