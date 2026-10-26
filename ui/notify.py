"""Уведомления: звук + запись в файл."""

import os
from datetime import datetime
from pathlib import Path

import config
from core.logger import get_logger

log = get_logger(__name__)


def notify_signal(signal, paper_trade: dict | None = None) -> None:
    """
    Уведомляет о новом сигнале:
    - звук (Windows beep);
    - запись в storage/logs/notifications.txt.
    """
    # --- Звук ---
    try:
        import winsound

        # 2 коротких бипа — сигнал
        winsound.Beep(1000, 300)
        winsound.Beep(1500, 300)
    except Exception:
        pass  # не Windows или нет звука

    # --- Запись в файл ---
    try:
        notif_path = Path(config.NOTIFY_FILE)
        notif_path.parent.mkdir(parents=True, exist_ok=True)

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = (
            f"[{now}] {signal.direction.upper()} {signal.kind} "
            f"score={signal.strength_score:.1f} "
            f"entry={signal.entry_price:.3f} "
            f"stop={signal.stop_price:.3f} "
            f"take={signal.take_price:.3f}"
        )
        if paper_trade:
            line += f" | paper_id={paper_trade.get('id', '?')}"
        line += "\n"

        with open(notif_path, "a", encoding="utf-8") as f:
            f.write(line)

        log.info("notify: %s", line.strip())
    except Exception as e:
        log.error("notify: ошибка записи: %s", e)
