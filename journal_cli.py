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
from trader.analytics import compute_stats

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
    from trader.paper import init_paper_table
    from trader.analytics import paper_stats

    with journal.connect_journal() as conn:
        init_paper_table(conn)
        
        if getattr(args, "no_slippage", False):
            import config
            config.PAPER_USE_MARKET_PRICE = False
            print("⚠️  --no-slippage: entry = close (сравнение, не пессимистично)\n")

        s = paper_stats(
            conn,
            since=args.since,
            until=args.until,
            symbol=args.symbol,
            known_only=getattr(args, "known_only", False),
            min_n=getattr(args, "min_n", 0),
            experiment=getattr(args, "experiment", None),
        )

    print()
    print(f"Всего: {s['total']} (закрытых {s['closed']}, открытых {s['open']})")
    print(f"  Win:      {s['win']}")
    print(f"  Loss:     {s['loss']}")
    print(f"  Timeout:  {s['timeout']}")
    if s["winrate"] is not None:
        wr_ci = s.get("winrate_ci")
        if wr_ci:
            print(
                f"  Winrate:  {s['winrate']}% (без timeout)"
                f" [{wr_ci[0]:.1f}%, {wr_ci[1]:.1f}%]"
            )
        else:
            print(f"  Winrate:  {s['winrate']}% (без timeout) [CI: n<5]")
    else:
        print("  Winrate:  —")
    print(f"  Total PnL: {s['total_points']:+.1f} pts / {s['total_rub']:+.2f} ₽")
    print(
        f"  Депозит: {s['virtual_deposit_start']:.0f} ₽ → {s['virtual_deposit_end']:.2f} ₽ ({s['virtual_pnl_pct']:+.2f}%)"
    )
    print(f"  Max drawdown: {s['max_drawdown_pct']:.2f}%")
    if s["avg_win_points"] is not None:
        print(f"  Avg win:   {s['avg_win_points']:+.1f} pts")
    if s["avg_loss_points"] is not None:
        print(f"  Avg loss:  {s['avg_loss_points']:+.1f} pts")

    # --- T-04: PF / Exp / Winrate с bootstrap CI ---
    def _fmt_ci(ci, fmt: str, sep: str = " ") -> str:
        """Форматирует CI: ' [low, high]' или ' [CI: n<5]'."""
        if ci is None:
            return " [CI: n<5]"
        return f" [{fmt.format(ci[0])}, {fmt.format(ci[1])}]"

    pf = s["profit_factor"]
    if pf is not None:
        print(
            f"  Profit factor: {pf:.2f}{_fmt_ci(s.get('profit_factor_ci'), '{:.2f}')}"
        )
    else:
        print("  Profit factor: —")

    exp = s["expectancy"]
    if exp is not None:
        print(
            f"  Expectancy: {exp:+.1f} pts"
            f"{_fmt_ci(s.get('expectancy_ci'), '{:+.1f}')}"
        )
    else:
        print("  Expectancy: —")

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
                    # --- NEW: expectancy ---
                    (
                        f"{b.get('expectancy', 0):+.1f}"
                        if b.get("expectancy") is not None
                        else "—"
                    ),
                ]
            )
        print(
            tabulate(
                rows,
                headers=["", "Всего", "W", "L", "T", "Pts", "Rub", "Exp"],
                tablefmt="rounded_outline",
            )
        )

    _print_group("По типу сигнала", s["by_kind"])
    _print_group("По MFE ratio (тейк)", s["by_mfe_ratio"])
    _print_group("По тренду на входе", s["by_trend"])
    _print_group("По дневному тренду", s["by_day_trend"])
    _print_group("По недельному тренду", s["by_week_trend"])
    _print_group("По недельному тренду × направление", s["by_week_trend_direction"])
    _print_group("По состоянию рынка", s["by_market_state"])
    _print_group("По ADX", s["by_adx"])
    _print_group("По стакану (bid/ask)", s["by_pressure"])
    _print_group("По скорости закрытия (баров)", s["by_bars"])
    _print_group("По сессии", s["by_session"])
    _print_group("По часу", s["by_hour"])
    _print_group("По дню недели", s["by_weekday"])
    _print_group("По RSI на входе", s["by_rsi"])
    _print_group("По волатильности (ATR percentile)", s["by_atr_percentile"])
    _print_group("По partial_day (день завершён?)", s["by_partial_day"])
    _print_group("По volume ratio", s.get("by_volume_ratio", {}))
    _print_group("По MAE ratio (стоп)", s.get("by_mae_ratio", {}))
    _print_group("По take_source", s.get("by_take_source", {}))
    _print_group("По day_range_atr (волатильность)", s.get("by_day_range_atr", {}))

    # by_score — сортируем по возрастанию score, с CI
    if s["by_score"]:
        print()
        print("── По score " + "─" * 40)
        rows = []
        for key in sorted(s["by_score"].keys()):
            b = s["by_score"][key]
            pf_ci = b.get("pf_ci")
            exp_ci = b.get("exp_ci")
            wr_ci = b.get("winrate_ci")

            pf_str = "—"
            if pf_ci:
                pf_str = f"[{pf_ci[0]:.2f}, {pf_ci[1]:.2f}]"
            elif b["total"] >= 5:
                pf_str = "n/a"

            exp_str = "—"
            if exp_ci:
                exp_str = f"[{exp_ci[0]:+.1f}, {exp_ci[1]:+.1f}]"
            elif b["total"] >= 5:
                exp_str = "n/a"

            wr_str = "—"
            if wr_ci:
                wr_str = f"[{wr_ci[0]:.1f}%, {wr_ci[1]:.1f}%]"
            elif b["total"] >= 5:
                wr_str = "n/a"

            rows.append(
                [
                    key,
                    b["total"],
                    b["win"],
                    b["loss"],
                    b["timeout"],
                    f"{b['points']:+.1f}",
                    f"{b['rub']:+.2f}",
                    pf_str,
                    exp_str,
                    wr_str,
                ]
            )
        print(
            tabulate(
                rows,
                headers=[
                    "score",
                    "Всего",
                    "W",
                    "L",
                    "T",
                    "Pts",
                    "Rub",
                    "PF CI",
                    "Exp CI",
                    "Winrate CI",
                ],
                tablefmt="rounded_outline",
            )
        )

    return 0


def cmd_paper_trades(args) -> int:
    """Показать paper-сделки."""
    from tabulate import tabulate

    with journal.connect_journal() as conn:
        from trader.paper import init_paper_table

        init_paper_table(conn)

        where = []
        params = []
        if args.open:
            where.append("result = 'open'")
        if args.symbol:
            where.append("symbol = ?")
            params.append(args.symbol)

        where_sql = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(
            f"SELECT * FROM paper_trades {where_sql} ORDER BY id DESC LIMIT ?",
            (*params, args.limit),
        ).fetchall()

    if not rows:
        print("Paper-сделок нет.")
        return 0

    table_rows = []
    for r in rows:
        row_data = [
            r["id"],
            r["direction"].upper(),
            r["kind"],
            f"{r['strength_score'] or 0:.1f}",
            f"{r['entry_price']:.3f}",
            f"{r['stop_price']:.3f}",
            f"{r['take_price']:.3f}",
            f"{r['exit_price']:.3f}" if r["exit_price"] else "—",
            r["result"],
            f"{r['result_points']:+.1f}" if r["result_points"] is not None else "—",
            f"{r['result_rub']:+.2f}" if r["result_rub"] is not None else "—",
            r["bars_to_close"] or "—",
            r["created_at"][5:16],
        ]
        if args.wide:
            row_data.extend(
                [
                    f"{r['adx_at_open']:.1f}" if r["adx_at_open"] is not None else "—",
                    r["week_trend_at_open"] or "—",
                    f"{r['bid_vol']:.0f}" if r["bid_vol"] is not None else "—",
                    f"{r['ask_vol']:.0f}" if r["ask_vol"] is not None else "—",
                    f"{r['risk_reward']:.2f}" if r["risk_reward"] is not None else "—",
                    (
                        f"{r['market_price_at_open']:.3f}"
                        if r["market_price_at_open"] is not None
                        else "—"
                    ),
                    f"{r['size'] or 1}",
                    (
                        f"{r['volume_ratio_at_open']:.2f}"
                        if r["volume_ratio_at_open"] is not None
                        else "—"
                    ),
                ]
            )
        table_rows.append(row_data)

    headers = [
        "ID",
        "Dir",
        "Kind",
        "Score",
        "Entry",
        "Stop",
        "Take",
        "Exit",
        "Result",
        "Pts",
        "Rub",
        "Bars",
        "Created",
    ]
    if args.wide:
        headers.extend(["ADX", "Week", "Bid", "Ask", "R:R", "Vol", "Mkt", "Size"])

    print(
        tabulate(
            table_rows,
            headers=headers,
            tablefmt="psql",
        )
    )

    from trader.paper import _colored, GREEN, RED, YELLOW

    win = sum(1 for r in rows if r["result"] == "win")
    loss = sum(1 for r in rows if r["result"] == "loss")
    open_count = sum(1 for r in rows if r["result"] == "open")
    total_pts = sum(r["result_points"] or 0 for r in rows)
    total_rub = sum(r["result_rub"] or 0 for r in rows)

    print()
    print(
        f"  Win: {_colored(str(win), GREEN)}  "
        f"Loss: {_colored(str(loss), RED)}  "
        f"Open: {_colored(str(open_count), YELLOW)}  |  "
        f"Total: {_colored(f'{total_pts:+.1f} pts', GREEN if total_pts >= 0 else RED)} / "
        f"{_colored(f'{total_rub:+.2f} ₽', GREEN if total_rub >= 0 else RED)}"
    )

    return 0


def cmd_paper_export(args) -> int:
    """Экспорт paper_trades в CSV."""
    from trader.paper_export import export_paper_trades

    with journal.connect_journal() as conn:
        from trader.paper import init_paper_table

        init_paper_table(conn)

        count = export_paper_trades(
            conn,
            output_path=args.output,
            since=args.since,
            until=args.until,
            symbol=args.symbol,
        )

    if count == 0:
        print("❌ Нет данных для экспорта")
        return 1

    print(f"✅ Экспортировано {count} записей → {args.output}")
    return 0


def cmd_paper_vs_real(args) -> int:
    """Сравнение paper entry vs market_price_at_open."""
    from trader.paper_vs_real import paper_vs_real_stats

    with journal.connect_journal() as conn:
        from trader.paper import init_paper_table

        init_paper_table(conn)

        s = paper_vs_real_stats(
            conn,
            since=args.since,
            until=args.until,
            symbol=args.symbol,
        )

    print()
    print(f"Всего сделок: {s['total']}")
    print(f"С market_price: {s['with_market']}")

    if s["with_market"] == 0:
        print("\n⚠️ Нет сделок с market_price_at_open")
        print("   (старые сделки — до миграции, или ALOR не отвечал)")
        return 0

    overall = s["overall"]
    print(f"\n── Лаг (market - entry) в пунктах ──")
    print(f"  Средний: {overall['avg']:+.1f}")
    print(f"  Медиана: {overall['median']:+.1f}")
    print(f"  Мин: {overall['min']:+.1f}")
    print(f"  Макс: {overall['max']:+.1f}")

    print(f"\n── По направлению ──")
    for d in ("long", "short"):
        st = s["by_direction"][d]
        if st["count"] > 0:
            print(
                f"  {d.upper():5} n={st['count']:2} avg={st['avg']:+.1f} median={st['median']:+.1f}"
            )

    print(f"\n── По результату ──")
    for res in ("win", "loss", "open"):
        st = s["by_result"][res]
        if st["count"] > 0:
            print(
                f"  {res.upper():5} n={st['count']:2} avg={st['avg']:+.1f} median={st['median']:+.1f}"
            )

    return 0


def cmd_paper_skipped(args) -> int:
    """T-05: заблокированные сигналы по reason."""
    from trader.paper import init_paper_table
    from trader.paper_db import get_skipped_stats

    with journal.connect_journal() as conn:
        init_paper_table(conn)
        s = get_skipped_stats(
            conn,
            since=args.since,
            until=args.until,
            symbol=args.symbol,
            experiment=getattr(args, "experiment", None),
        )

    print()
    print(f"Всего skipped: {s['total']}")
    if s["total"] == 0:
        print("  (нет записей — paper_skipped пуст или все сигналы прошли)")
        return 0

    print()
    print("── По reason " + "─" * 40)
    rows = []
    for reason, b in sorted(s["by_reason"].items(), key=lambda x: -x[1]["total"]):
        rows.append([reason, b["total"], f"{b['pct']:.1f}%"])
    print(
        tabulate(
            rows,
            headers=["reason", "n", "pct"],
            tablefmt="rounded_outline",
        )
    )

    print()
    print("── По kind " + "─" * 40)
    rows = [[k, v] for k, v in sorted(s["by_kind"].items(), key=lambda x: -x[1])]
    print(tabulate(rows, headers=["kind", "n"], tablefmt="rounded_outline"))

    print()
    print("── По направлению " + "─" * 40)
    rows = [[d, v] for d, v in sorted(s["by_direction"].items(), key=lambda x: -x[1])]
    print(tabulate(rows, headers=["direction", "n"], tablefmt="rounded_outline"))
    if config.EXPERIMENT_ID:
        print(f"  Experiment (current): {config.EXPERIMENT_ID}")
    else:
        print("  Experiment: baseline (вне эксперимента)")

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
        "--known-only",
        action="store_true",
        help="Убрать unknown в week_trend/market_state/RSI/ATR (чистые разрезы)",
    )
    p_paper.add_argument(
        "--no-slippage",
        action="store_true",
        help="T-24: считать PnL по close (без market_price_at_open) — для сравнения",
    )
    p_paper.add_argument(
        "--min-n",
        type=int,
        default=0,
        help="Показывать только бакеты с n >= N (например, 10)",
    )
    p_paper.add_argument("--since", default=None, help="С даты (ISO)")
    p_paper.add_argument("--until", default=None, help="До даты (ISO)")
    p_paper.add_argument("--symbol", default=None, help="Фильтр по тикеру")
    p_paper.set_defaults(func=cmd_paper_stats)

    # paper-export
    p_export = sub.add_parser("paper-export", help="Экспорт paper_trades в CSV")
    p_export.add_argument(
        "--output",
        default="storage/exports/paper_trades.csv",
        help="Путь к CSV",
    )
    p_export.add_argument("--since", default=None, help="С даты (ISO)")
    p_export.add_argument("--until", default=None, help="До даты (ISO)")
    p_export.add_argument("--symbol", default=None, help="Фильтр по тикеру")
    p_export.set_defaults(func=cmd_paper_export)

    # paper-trades
    p_pt = sub.add_parser("paper-trades", help="Показать paper-сделки")
    p_pt.add_argument("--open", action="store_true", help="Только открытые")
    p_pt.add_argument("--limit", type=int, default=50)
    p_pt.add_argument("--symbol", default=None, help="Фильтр по тикеру")
    p_pt.add_argument(
        "--wide", action="store_true", help="Показать ADX, Bid/Ask, R:R, Mkt"
    )
    p_pt.set_defaults(func=cmd_paper_trades)

    # paper-vs-real
    p_vs = sub.add_parser("paper-vs-real", help="Сравнение paper entry vs market")
    p_vs.add_argument("--since", default=None, help="С даты (ISO)")
    p_vs.add_argument("--until", default=None, help="До даты (ISO)")
    p_vs.add_argument("--symbol", default=None, help="Фильтр по тикеру")
    p_vs.set_defaults(func=cmd_paper_vs_real)

    # paper-skipped (T-05)
    p_skip = sub.add_parser("paper-skipped", help="Заблокированные сигналы (T-05)")
    p_skip.add_argument("--since", default=None, help="С даты (ISO)")
    p_skip.add_argument("--until", default=None, help="До даты (ISO)")
    p_skip.add_argument("--symbol", default=None, help="Фильтр по тикеру")
    p_skip.add_argument("--experiment", default=None, help="Фильтр по EXPERIMENT_ID")
    p_skip.set_defaults(func=cmd_paper_skipped)

    p_paper.add_argument(
        "--experiment",
        default=None,
        help="Фильтр по EXPERIMENT_ID (например, EXP-20261122-01)",
    )
    args = parser.parse_args()

    journal.init_db()

    # --- Рекомендация stop/take (по MFE/MAE, Задача 5) ---
    try:
        from scripts.optimize_stops import STOP_GRID, TAKE_GRID, run_grid
        from core.instruments import get_instrument
        from trader.paper import init_paper_table

        # Достаём сделки с MFE/MAE
        with journal.connect_journal() as conn:
            init_paper_table(conn)
            rows = conn.execute("""
                SELECT * FROM paper_trades
                WHERE mfe_points IS NOT NULL AND mae_points IS NOT NULL
                  AND result IN ('win', 'loss', 'timeout')
                  AND mfe_source IN ('live', 'backfill')
                """).fetchall()

        if len(rows) >= 5:
            inst = get_instrument(config.DEFAULT_INSTRUMENT)
            rows_dict = [dict(r) for r in rows]

            # Текущее
            cur = run_grid(rows_dict, inst, config.STOP_ATR_MULT, config.TAKE_ATR_MULT)

            # Лучшее из сетки
            best = None
            for stop in STOP_GRID:
                for take in TAKE_GRID:
                    res = run_grid(rows_dict, inst, stop, take)
                    if res["pf"] is not None and (
                        best is None or (res["pf"] or 0) > (best["pf"] or 0)
                    ):
                        best = res

            print()
            print("── Рекомендация stop/take (по MFE/MAE) ──")
            print(
                f"  Текущее:   stop={config.STOP_ATR_MULT:.1f}, take={config.TAKE_ATR_MULT:.1f} | "
                f"n={cur['n']} | PF={cur['pf']} | Exp={cur['exp']}"
            )
            if best:
                print(
                    f"  Best(grid): stop={best['stop']:.1f}, take={best['take']:.1f} | "
                    f"n={best['n']} | PF={best['pf']} | Exp={best['exp']}"
                )

            conf = "low (n<30, предварительно)" if len(rows) < 30 else "medium (n>=30)"
            print(f"  Confidence: {conf} — НЕ менять config автоматически")
    except Exception as e:
        print(f"\n(Рекомендация stop/take недоступна: {e})")

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
