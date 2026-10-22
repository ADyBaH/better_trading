"""
Раннер. Каждые 20 минут:
    1. Запускает анализ.
    2. Сохраняет результат в logs/YYYY-MM-DD/analysis_HH-MM-SS.{json,txt}.
    3. Спит 20 минут.
    4. Повторяет.

Остановка: Ctrl+C.
"""

import sys
import time
from datetime import datetime
from pathlib import Path

import config
from core.logger import setup_logging, get_logger
from core.analyzer import analyze
from ui.render_console import render_console_to_string
from ui.render_json import render_json

INTERVAL_MIN = 5
LOGS_DIR = Path(config.LOG_PATH).parent


def save_analysis(result) -> tuple[Path, Path]:
    """
    Дописывает результат в logs/YYYY-MM-DD/analysis_YYYY-MM-DD.json и .txt.
    Возвращает (json_path, txt_path).
    """
    now = datetime.now()
    date_dir = LOGS_DIR / now.strftime("%Y-%m-%d")
    date_dir.mkdir(parents=True, exist_ok=True)

    # Имя файла с полной датой (например, analysis_2026-10-22.json)
    date_str = now.strftime("%Y-%m-%d")
    json_path = date_dir / f"analysis_{date_str}.json"
    txt_path = date_dir / f"analysis_{date_str}.txt"

    # JSON Lines: каждый цикл — одна строка
    json_line = render_json(result, mode="full").replace("\n", " ")
    with open(json_path, "a", encoding="utf-8") as f:
        f.write(json_line + "\n")

    # Текстовый дашборд: разделитель между циклами
    txt_block = render_console_to_string(result)
    with open(txt_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 70}\n")
        f.write(f"  {now.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"{'=' * 70}\n")
        f.write(txt_block)
        f.write("\n")

    return json_path, txt_path


def run_once(log) -> bool:
    """Один цикл: анализ + сохранение. True если успех."""
    try:
        result = analyze()
        if result is None:
            log.error("analyze() вернул None")
            return False

        json_path, txt_path = save_analysis(result)

        # --- Paper-tracking ---
        paper_created = 0
        paper_closed = 0
        new_trades = []
        closed_trades = []
        if config.PAPER_ENABLED:
            from trader.journal import connect_journal
            from trader.paper import (
                init_paper_table,
                save_signal_as_paper,
                resolve_open_trades,
                format_paper_trade_short,  # ← добавить
                format_paper_trade_result,  # ← добавить
            )

            try:
                with connect_journal() as conn:
                    init_paper_table(conn)

                    # Запоминаем max id до создания новых
                    max_id_before = conn.execute(
                        "SELECT COALESCE(MAX(id), 0) FROM paper_trades"
                    ).fetchone()[0]

                    # --- Получаем стакан (если ALOR) ---
                    bid_vol = None
                    ask_vol = None
                    if config.DATA_PROVIDER == "alor" and result.signals:
                        from data.api_alor import get_order_book_pressure_sync

                        try:
                            ob = get_order_book_pressure_sync(result.symbol)
                            bid_vol = ob["bid_vol"]
                            ask_vol = ob["ask_vol"]
                            log.info(
                                "order_book: bid=%.0f, ask=%.0f, pressure=%.1f%%",
                                bid_vol,
                                ask_vol,
                                ob["pressure_pct"],
                            )
                        except Exception as e:
                            log.debug("order_book не получен: %s", e)

                    # --- Создаём paper-сделки ---
                    paper_created = save_signal_as_paper(
                        conn,
                        result.signals,
                        result,
                        source_analysis_path=str(json_path),
                        bid_vol=bid_vol,
                        ask_vol=ask_vol,
                    )

                    # Запоминаем id закрытых до резолва
                    open_ids_before = set(
                        r["id"]
                        for r in conn.execute(
                            "SELECT id FROM paper_trades WHERE result = 'open'"
                        ).fetchall()
                    )

                    paper_closed = resolve_open_trades(
                        conn, result.symbol, result.timestamp
                    )

                    # Новые сделки
                    if paper_created > 0:
                        new_trades = conn.execute(
                            "SELECT * FROM paper_trades WHERE id > ? ORDER BY id",
                            (max_id_before,),
                        ).fetchall()

                    # Только что закрытые
                    if paper_closed > 0 and open_ids_before:
                        closed_trades = conn.execute(
                            f"SELECT * FROM paper_trades WHERE id IN ({','.join('?' * len(open_ids_before))}) "
                            "AND result != 'open' ORDER BY id",
                            tuple(open_ids_before),
                        ).fetchall()

                log.info("paper: создано %d, закрыто %d", paper_created, paper_closed)
            except Exception as e:
                log.exception("paper-tracking упал: %s", e)
        # --- /Paper-tracking ---

        # Краткий вывод в консоль
        print(f"\n{'═' * 70}")
        print(
            f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  |  {result.symbol}  |  Цена: {result.current_price:.3f}"
        )
        print(
            f"  Тренд: {result.indicators.trend} (голосов {result.indicators.vote_sum:+d})  |  "
            f"День: {result.indicators.day_trend}  |  Структура: {result.indicators.structure}"
        )
        for s in result.signals:
            print(
                f"    → {s.direction.upper()} {s.kind} ({s.strength}, score={s.strength_score:.1f})"
            )
        print(f"  Сохранено: {json_path.name}, {txt_path.name}")
        print(f"{'═' * 70}")
        print(f"  Сигналов: {len(result.signals)}")
        if config.PAPER_ENABLED:
            print(f"  paper: создано {paper_created}, закрыто {paper_closed}")
            for t in new_trades:
                print(f"    + {format_paper_trade_short(t)}")
            for t in closed_trades:
                print(f"    ✓ {format_paper_trade_result(t)}")

        return True

    except KeyboardInterrupt:
        raise
    except Exception as e:
        log.exception("Ошибка в цикле: %s", e)
        return False


def main():
    print("\033[92mТЕСТ ЦВЕТА\033[0m")
    setup_logging()
    log = get_logger(__name__)

    log.info("=== runner стартует (интервал %d мин) ===", INTERVAL_MIN)
    print(f"\nРаннер запущен. Интервал: {INTERVAL_MIN} мин.")
    print(f"Логи: {LOGS_DIR}/YYYY-MM-DD/")
    print(f"Остановка: Ctrl+C\n")

    cycle = 0
    try:
        while True:
            cycle += 1
            log.info("Цикл #%d", cycle)
            print(f"\n[цикл #{cycle}] {datetime.now().strftime('%H:%M:%S')}")

            run_once(log)

            # Спим с периодическими проверками (чтобы Ctrl+C срабатывал быстро)
            next_run = datetime.now().timestamp() + INTERVAL_MIN * 60
            print(
                f"  Следующий запуск ~{datetime.fromtimestamp(next_run).strftime('%H:%M:%S')}"
            )
            while datetime.now().timestamp() < next_run:
                time.sleep(1)

    except KeyboardInterrupt:
        log.info("=== runner остановлен (Ctrl+C) ===")
        print(f"\nРаннер остановлен. Всего циклов: {cycle}")


if __name__ == "__main__":
    main()
