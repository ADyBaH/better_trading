"""
CLI для журнала сделок.
Примеры:
    python journal_cli.py add
    python journal_cli.py list
    python journal_cli.py list --open
    python journal_cli.py close 1 12.473
    python journal_cli.py stats
"""

import argparse
import sys
from datetime import datetime

from tabulate import tabulate

from core.logger import setup_logging, get_logger
from trader import journal
from trader.stats import compute_stats

import config

# ============================================================
# Форматирование
# ============================================================


def _fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "—"
    return dt.strftime("%Y-%m-%d %H:%M")


def _fmt_result(pts: float | None, rub: float | None) -> str:
    if pts is None:
        return "—"
    sign = "+" if pts > 0 else ""
    rub_sign = "+" if (rub or 0) > 0 else ""
    return f"{sign}{pts:.1f} pts / {rub_sign}{rub or 0:.2f} ₽"


def _print_trades(trades: list[journal.Trade], wide: bool = False) -> None:
    if not trades:
        print("Сделок нет.")
        return

    comment_limit = 100 if wide else 30

    rows = []
    for t in trades:
        rows.append(
            [
                t.id,
                _fmt_dt(t.datetime_open),
                t.direction.upper(),
                f"{t.entry_price:.3f}",
                f"{t.exit_price:.3f}" if t.exit_price else "—",
                _fmt_result(t.result_points, t.result_rub),
                t.signal_kind or "manual",
                t.signal_strength or "",
                t.comment[:comment_limit],
            ]
        )

    headers = [
        "ID",
        "Открыта",
        "Напр",
        "Вход",
        "Выход",
        "Результат",
        "Сигнал",
        "Сила",
        "Коммент",
    ]
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))


def _print_stats(s) -> None:
    print()
    print(f"Всего сделок: {s.total} (закрытых {s.closed}, открытых {s.open})")
    print(f"Winrate: {s.winrate}%  ({s.wins}W / {s.losses}L / {s.breakeven}BE)")
    print(f"Total PnL: {s.total_points:+.1f} pts / {s.total_rub:+.2f} ₽")
    avg_win_str = f"{s.avg_win_points:+.1f} pts" if s.wins > 0 else "—"
    avg_loss_str = f"{s.avg_loss_points:+.1f} pts" if s.losses > 0 else "—"
    best_str = f"{s.best_points:+.1f}" if s.closed > 0 else "—"
    worst_str = f"{s.worst_points:+.1f}" if s.losses > 0 else "—"

    print(f"Средний выигрыш: {avg_win_str}")
    print(f"Средний проигрыш: {avg_loss_str}")
    print(f"Лучшая: {best_str}  |  Худшая: {worst_str}")

    if s.by_signal_kind:
        print()
        print("── По типу сигнала " + "─" * 40)
        rows = []
        for kind, b in sorted(s.by_signal_kind.items()):
            rows.append(
                [
                    kind,
                    b["total"],
                    b["wins"],
                    b["losses"],
                    f"{b['points']:+.1f}",
                    f"{b['rub']:+.2f}",
                ]
            )
        print(
            tabulate(
                rows,
                headers=["Тип", "Всего", "W", "L", "Pts", "Rub"],
                tablefmt="rounded_outline",
            )
        )

    if s.by_signal_strength:
        print()
        print("── По силе сигнала " + "─" * 40)
        rows = []
        for strength, b in sorted(s.by_signal_strength.items()):
            rows.append(
                [
                    strength,
                    b["total"],
                    b["wins"],
                    b["losses"],
                    f"{b['points']:+.1f}",
                    f"{b['rub']:+.2f}",
                ]
            )
        print(
            tabulate(
                rows,
                headers=["Сила", "Всего", "W", "L", "Pts", "Rub"],
                tablefmt="rounded_outline",
            )
        )

    if s.by_tags:
        print()
        print("── По тегам " + "─" * 40)
        rows = []
        for tag, b in sorted(s.by_tags.items()):
            rows.append(
                [
                    tag,
                    b["total"],
                    b["wins"],
                    b["losses"],
                    f"{b['points']:+.1f}",
                    f"{b['rub']:+.2f}",
                ]
            )
        print(
            tabulate(
                rows,
                headers=["Тег", "Всего", "W", "L", "Pts", "Rub"],
                tablefmt="rounded_outline",
            )
        )


def cmd_delete(args) -> int:
    """Удаляет сделку по id."""
    t = journal.get_trade(args.id)
    if t is None:
        print(f"Сделка #{args.id} не найдена.")
        return 1

    confirm = input(
        f"Удалить сделку #{args.id} "
        f"({t.direction.upper()} @ {t.entry_price}, "
        f"{_fmt_dt(t.datetime_open)})? [y/N]: "
    )
    if confirm.lower() != "y":
        print("Отменено.")
        return 0

    with journal._connect() as conn:
        conn.execute("DELETE FROM trades WHERE id = ?", (args.id,))

    print(f"✓ Сделка #{args.id} удалена.")
    return 0


# ============================================================
# Интерактивный ввод
# ============================================================


def _ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def cmd_add(args) -> int:
    """Интерактивно добавляет сделку."""
    print("── Новая сделка ──")
    direction = _ask("Направление (long/short)").lower()
    if direction not in ("long", "short"):
        print(f"Ошибка: направление должно быть long или short, получено: {direction}")
        return 1

    try:
        entry = float(_ask("Цена входа"))
    except ValueError:
        print("Ошибка: цена входа должна быть числом")
        return 1

    size = int(_ask("Размер (контрактов)", "1") or "1")

    stop_str = _ask("Стоп (Enter — пропустить)")
    stop = float(stop_str) if stop_str else None

    take_str = _ask("Тейк (Enter — пропустить)")
    take = float(take_str) if take_str else None

    comment = _ask("Комментарий")
    tags_str = _ask("Теги (через запятую)")
    tags = [t.strip() for t in tags_str.split(",") if t.strip()]

    signal_kind = _ask("Тип сигнала (bounce/breakout/trend_level, Enter — manual)")
    signal_strength = _ask("Сила сигнала (weak/medium/strong)")
    score_str = _ask("Score сигнала", "0")
    try:
        signal_score = float(score_str)
    except ValueError:
        signal_score = 0.0

    trade = journal.Trade(
        direction=direction,
        entry_price=entry,
        datetime_open=datetime.now(),
        size=size,
        stop_price=stop,
        take_price=take,
        comment=comment,
        tags=tags,
        signal_kind=signal_kind,
        signal_strength=signal_strength,
        signal_score=signal_score,
    )

    tid = journal.add_trade(trade)
    print(f"\n✓ Сделка #{tid} добавлена.")
    return 0


def cmd_list(args) -> int:
    trades = journal.list_trades(limit=args.limit, only_open=args.open)
    _print_trades(trades, wide=args.wide)
    return 0


def cmd_close(args) -> int:
    t = journal.get_trade(args.id)
    if t is None:
        print(f"Сделка #{args.id} не найдена.")
        return 1

    if t.is_closed:
        print(f"Сделка #{args.id} уже закрыта.")
        return 1

    comment = _ask("Комментарий к закрытию (Enter — пропустить)")
    journal.close_trade(args.id, exit_price=args.price, comment=comment)

    t = journal.get_trade(args.id)
    print(
        f"✓ Сделка #{args.id} закрыта. "
        f"Результат: {t.result_points:+.1f} pts / {t.result_rub:+.2f} ₽"
    )
    return 0


def cmd_stats(args) -> int:
    s = compute_stats(limit=args.limit)
    _print_stats(s)
    return 0


# ============================================================
# main
# ============================================================


def main() -> int:
    setup_logging()
    log = get_logger(__name__)

    parser = argparse.ArgumentParser(
        description="Журнал сделок для CNYRUBF.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # add
    p_add = sub.add_parser("add", help="Добавить сделку (интерактивно)")
    p_add.set_defaults(func=cmd_add)

    # list
    p_list = sub.add_parser("list", help="Показать последние сделки")
    p_list.add_argument("--limit", type=int, default=20)
    p_list.add_argument("--open", action="store_true", help="Только открытые")
    p_list.add_argument("--wide", action="store_true", help="Не обрезать комментарии")
    p_list.set_defaults(func=cmd_list)

    # close
    p_close = sub.add_parser("close", help="Закрыть сделку")
    p_close.add_argument("id", type=int, help="ID сделки")
    p_close.add_argument("price", type=float, help="Цена выхода")
    p_close.set_defaults(func=cmd_close)

    # stats
    p_stats = sub.add_parser("stats", help="Статистика по журналу")
    p_stats.add_argument("--limit", type=int, default=1000)
    p_stats.set_defaults(func=cmd_stats)

    # delete  ← НОВЫЙ БЛОК
    p_del = sub.add_parser("delete", help="Удалить сделку")
    p_del.add_argument("id", type=int, help="ID сделки")
    p_del.set_defaults(func=cmd_delete)

    args = parser.parse_args()
    journal.init_db()

    return args.func(args)


def cmd_delete(args) -> int:
    t = journal.get_trade(args.id)
    if t is None:
        print(f"Сделка #{args.id} не найдена.")
        return 1
    confirm = input(
        f"Удалить сделку #{args.id} ({t.direction} @ {t.entry_price})? [y/N]: "
    )
    if confirm.lower() != "y":
        print("Отменено.")
        return 0
    with journal._connect() as conn:
        conn.execute("DELETE FROM trades WHERE id = ?", (args.id,))
    print(f"✓ Сделка #{args.id} удалена.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
