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

    from core.instruments import get_instrument

    comment_limit = 100 if wide else 30

    rows = []
    for t in trades:
        try:
            inst = get_instrument(t.symbol)
            commission_default = inst.commission_round * t.size
        except ValueError:
            commission_default = 0.0

        commission = (
            t.commission_rub if t.commission_rub is not None else commission_default
        )

        rows.append(
            [
                t.id,
                t.symbol,
                _fmt_dt(t.datetime_open),
                t.direction.upper(),
                f"{t.entry_price:.3f}",
                f"{t.exit_price:.3f}" if t.exit_price else "—",
                _fmt_result(t.result_points, t.result_rub),
                f"{commission:.2f}",
                t.signal_kind or "manual",
                t.signal_strength or "",
                t.comment[:comment_limit],
            ]
        )

    headers = [
        "ID",
        "Символ",
        "Открыта",
        "Напр",
        "Вход",
        "Выход",
        "Результат",
        "Комис",
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
    from core.instruments import get_instrument, list_instruments
    from datetime import datetime as dt

    print("── Новая сделка ──")

    # Символ
    available = list_instruments()
    default_symbol = config.DEFAULT_INSTRUMENT
    symbol = _ask(f"Символ ({'/'.join(available)})", default_symbol).upper()
    try:
        inst = get_instrument(symbol)
    except ValueError as e:
        print(f"Ошибка: {e}")
        return 1

    # Направление
    direction_raw = _ask("Направление (l/s)").lower().strip()
    if direction_raw in ("l", "long"):
        direction = "long"
    elif direction_raw in ("s", "short"):
        direction = "short"
    else:
        print(f"Ошибка: направление должно быть l или s, получено: {direction_raw}")
        return 1

    # Цена входа
    try:
        entry = float(_ask("Цена входа"))
    except ValueError:
        print("Ошибка: цена входа должна быть числом")
        return 1

    # Цена выхода — только если --closed
    exit_price = None
    datetime_close = None
    if getattr(args, "closed", False):
        try:
            exit_price = float(_ask("Цена выхода"))
        except ValueError:
            print("Ошибка: цена выхода должна быть числом")
            return 1
        datetime_close = dt.now()

    # Размер
    size = int(_ask("Размер (контрактов)", "1") or "1")

    # Стоп / Тейк
    stop_str = _ask("Стоп (Enter — пропустить)")
    stop = float(stop_str) if stop_str else None

    take_str = _ask("Тейк (Enter — пропустить)")
    take = float(take_str) if take_str else None

    # Прочее
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

    # Комиссия
    default_comm = inst.commission_round * size
    print(
        f"\nКомиссия за круг: {inst.commission_round:.2f} ₽ × {size} = {default_comm:.2f} ₽"
    )
    comm_str = _ask("Переопределить комиссию (Enter — оставить)", "")
    commission_rub = float(comm_str) if comm_str else None

    # Создаём сделку
    trade = journal.Trade(
        symbol=symbol,
        direction=direction,
        entry_price=entry,
        datetime_open=dt.now(),
        size=size,
        stop_price=stop,
        take_price=take,
        comment=comment,
        tags=tags,
        signal_kind=signal_kind,
        signal_strength=signal_strength,
        signal_score=signal_score,
        commission_rub=commission_rub,
        exit_price=exit_price,
        datetime_close=datetime_close,
    )

    tid = journal.add_trade(trade)

    # Итог
    if exit_price is not None:
        t = journal.get_trade(tid)
        print(f"\n✓ Сделка #{tid} добавлена и закрыта.")
        print(f"   Результат: {t.result_points:+.1f} pts / {t.result_rub:+.2f} ₽")
    else:
        print(f"\n✓ Сделка #{tid} добавлена (открыта).")

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

    # Комиссия: переопределение
    comm_str = _ask("Переопределить комиссию (Enter — из инструмента)", "")
    commission = float(comm_str) if comm_str else None

    # Результат: override или из цены
    override_str = _ask("Override результата в пунктах (Enter — считать из цены)", "")
    override = float(override_str) if override_str else None

    note = _ask("Заметка о результате (Enter — пропустить)")

    if override is None:
        # Обычный путь: exit_price обязателен
        if args.price is None:
            print("Ошибка: без override нужно указать цену выхода.")
            return 1
        journal.close_trade(
            args.id,
            exit_price=args.price,
            comment=comment,
            commission=commission,
            result_note=note,
        )
    else:
        journal.close_trade(
            args.id,
            exit_price=args.price,  # может быть None
            comment=comment,
            commission=commission,
            result_override_points=override,
            result_note=note,
        )

    t = journal.get_trade(args.id)
    print(f"✓ Сделка #{args.id} закрыта.")
    print(f"   Пункты: {t.result_points:+.1f}")
    print(f"   Рубли (с учётом комиссии): {t.result_rub:+.2f} ₽")
    return 0


def cmd_stats(args) -> int:
    s = compute_stats(limit=args.limit)
    _print_stats(s)
    return 0


def cmd_paper_stats(args) -> int:
    """Статистика по paper_trades."""
    from trader.paper import paper_stats, init_paper_table

    with journal.connect_journal() as conn:
        init_paper_table(conn)
        s = paper_stats(
            conn,
            since=args.since,
            until=args.until,
            symbol=args.symbol,
        )

    print()
    print(f"Всего: {s['total']} (закрытых {s['closed']}, открытых {s['open']})")
    print(f"  Win:      {s['win']}")
    print(f"  Loss:     {s['loss']}")
    print(f"  Timeout:  {s['timeout']}")
    if s["winrate"] is not None:
        print(f"  Winrate:  {s['winrate']}% (без timeout)")
    else:
        print("  Winrate:  —")
    print(f"  Total PnL: {s['total_points']:+.1f} pts / {s['total_rub']:+.2f} ₽")
    if s["avg_win_points"] is not None:
        print(f"  Avg win:   {s['avg_win_points']:+.1f} pts")
    if s["avg_loss_points"] is not None:
        print(f"  Avg loss:  {s['avg_loss_points']:+.1f} pts")

    def _print_group(title: str, group: dict, sort_key=None):
        if not group:
            return
        print()
        print(f"── {title} " + "─" * 40)
        rows = []
        items = (
            sorted(group.items())
            if sort_key is None
            else sorted(group.items(), key=sort_key)
        )
        for key, b in items:
            rows.append(
                [
                    key,
                    b["total"],
                    b["win"],
                    b["loss"],
                    b["timeout"],
                    f"{b['points']:+.1f}",
                    f"{b['rub']:+.2f}",
                ]
            )
        print(
            tabulate(
                rows,
                headers=["", "Всего", "W", "L", "T", "Pts", "Rub"],
                tablefmt="rounded_outline",
            )
        )

    _print_group("По типу сигнала", s["by_kind"])
    _print_group("По тренду на входе", s["by_trend"])
    _print_group("По дневному тренду", s["by_day_trend"])

    # by_score — сортируем по возрастанию score
    if s["by_score"]:
        print()
        print("── По score " + "─" * 40)
        rows = []
        for key in sorted(s["by_score"].keys()):
            b = s["by_score"][key]
            rows.append(
                [
                    key,
                    b["total"],
                    b["win"],
                    b["loss"],
                    b["timeout"],
                    f"{b['points']:+.1f}",
                    f"{b['rub']:+.2f}",
                ]
            )
        print(
            tabulate(
                rows,
                headers=["score", "Всего", "W", "L", "T", "Pts", "Rub"],
                tablefmt="rounded_outline",
            )
        )

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
    p_add.add_argument(
        "--closed",
        action="store_true",
        help="Сделка уже закрыта — спросить цену выхода сразу",
    )
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
    p_close.add_argument(
        "price",
        type=float,
        nargs="?",
        default=None,
        help="Цена выхода (опционально, если используется --result)",
    )
    p_close.add_argument(
        "--result",
        type=float,
        dest="result_override",
        help="Override результата в пунктах",
    )
    p_close.add_argument(
        "--commission", type=float, help="Переопределить комиссию (руб)"
    )
    p_close.set_defaults(func=cmd_close)

    # stats
    p_stats = sub.add_parser("stats", help="Статистика по журналу")
    p_stats.add_argument("--limit", type=int, default=1000)
    p_stats.set_defaults(func=cmd_stats)

    # delete
    p_del = sub.add_parser("delete", help="Удалить сделку")
    p_del.add_argument("id", type=int, help="ID сделки")
    p_del.set_defaults(func=cmd_delete)

    # paper-stats
    p_paper = sub.add_parser("paper-stats", help="Статистика paper-trading")
    p_paper.add_argument(
        "--since", default=None, help="С даты (ISO, например 2026-10-17)"
    )
    p_paper.add_argument("--until", default=None, help="До даты (ISO)")
    p_paper.add_argument("--symbol", default=None, help="Фильтр по тикеру")
    p_paper.set_defaults(func=cmd_paper_stats)

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
