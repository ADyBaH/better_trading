"""
Точка входа. Собирает AnalysisResult и рендерит его в выбранный формат.

Примеры:
    python main.py                          # консольный дашборд
    python main.py --json                   # JSON nested
    python main.py --json=flat              # JSON flat
    python main.py --json=full              # JSON full (с метаданными)
    python main.py --console --json         # оба вывода
    python main.py --log                    # + logs/run_<ts>.log (технический)
    python main.py --save                   # + logs/analysis_<ts>.txt (дашборд)
    python main.py --json --save            # + logs/analysis_<ts>.json
    python main.py --log --save             # полный слепок запуска
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

import config
from core.logger import setup_logging, get_logger
from core.analyzer import analyze
from ui.render_console import render_console, render_console_to_string
from ui.render_json import render_json


# ============================================================
# Аргументы CLI
# ============================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trading assistant для CNYRUBF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # --- Вывод ---
    parser.add_argument(
        "--console",
        action="store_true",
        help="Вывести консольный дашборд",
    )
    parser.add_argument(
        "--json",
        nargs="?",
        const="nested",
        default=None,
        choices=["flat", "nested", "full"],
        help="Вывести JSON (flat / nested / full). Без значения = nested.",
    )

    # --- Сохранение ---
    parser.add_argument(
        "--log",
        action="store_true",
        help="Сохранить технический лог запуска в logs/run_<timestamp>.log",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Сохранить вывод рендерера в logs/analysis_<timestamp>.{txt|json}",
    )

    # --- Параметры анализа ---
    parser.add_argument(
        "--symbol",
        default=None,
        help=f"Тикер (по умолчанию {config.SYMBOL})",
    )
    parser.add_argument(
        "--timeframe",
        default=None,
        help=f"Таймфрейм анализа (по умолчанию {config.DEFAULT_TIMEFRAME})",
    )

    return parser.parse_args()


# ============================================================
# Логирование запуска
# ============================================================

def attach_run_logger() -> Path:
    """
    Добавляет второй FileHandler, пишущий в logs/run_<timestamp>.log.
    Возвращает путь к созданному файлу.
    """
    logs_dir = Path(config.LOG_PATH).parent
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run_log_path = logs_dir / f"run_{timestamp}.log"

    handler = logging.FileHandler(run_log_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(config.LOG_FORMAT, datefmt=config.LOG_DATE_FORMAT)
    )
    handler.setLevel(logging.DEBUG)   # в отдельный файл — всё, включая DEBUG
    logging.getLogger().addHandler(handler)

    return run_log_path


# ============================================================
# Сохранение вывода рендерера
# ============================================================

def save_output(
    result,
    output_kind: str,
    json_mode: str | None,
) -> Path:
    """
    Сохраняет вывод рендерера в logs/analysis_<timestamp>.<ext>.

    output_kind: 'console' | 'json'
    json_mode: 'flat' | 'nested' | 'full' (для json)
    """
    logs_dir = Path(config.LOG_PATH).parent
    logs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

    if output_kind == "json":
        ext = "json"
        content = render_json(result, mode=json_mode or "nested")
    else:
        ext = "txt"
        content = render_console_to_string(result)

    out_path = logs_dir / f"analysis_{timestamp}.{ext}"
    out_path.write_text(content, encoding="utf-8")
    return out_path


# ============================================================
# main
# ============================================================

def main() -> int:
    setup_logging()
    log = get_logger(__name__)

    args = parse_args()

    # --- Дополнительный лог запуска ---
    run_log_path = None
    if args.log:
        run_log_path = attach_run_logger()

    log.info("=== %s v%s стартует ===", config.SYMBOL_NAME, config.__version__)
    if run_log_path:
        log.info("Технический лог запуска: %s", run_log_path)

    # --- По умолчанию — console, если ничего не указано ---
    show_console = args.console or args.json is None
    show_json = args.json is not None

    # --- Анализ ---
    result = analyze(symbol=args.symbol, timeframe=args.timeframe)
    if result is None:
        log.error("Анализ не удался")
        return 1

    # --- Вывод ---
    saved_files = []

    if show_console:
        render_console(result)
        if args.save:
            path = save_output(result, "console", None)
            saved_files.append(path)

    if show_json:
        json_str = render_json(result, mode=args.json)
        print(json_str)
        if args.save:
            path = save_output(result, "json", args.json)
            saved_files.append(path)

    # --- Сообщение о сохранённых файлах ---
    if run_log_path:
        print(f"\n[лог запуска] {run_log_path}")
    for p in saved_files:
        print(f"[сохранён вывод] {p}")

    return 0


if __name__ == "__main__":
    sys.exit(main())