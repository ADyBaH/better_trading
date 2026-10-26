"""Тесты на ui/notify.py."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import tempfile
from ui.notify import notify_signal
from core.models import Signal

PASSED = 0
FAILED = 0


def check(name, actual, expected):
    global PASSED, FAILED
    if hasattr(actual, "item"):
        actual = actual.item()
    if actual == expected:
        PASSED += 1
        print(f"  ✅ {name}")
    else:
        FAILED += 1
        print(f"  ❌ {name}: expected {expected!r}, got {actual!r}")


def make_signal():
    return Signal(
        direction="short",
        kind="breakout",
        strength="medium",
        strength_score=2.0,
        entry_price=12.500,
        stop_price=12.530,
        take_price=12.440,
        matched_criteria=["A1", "B2"],
        reasons=[],
        level_price=12.500,
    )


def main():
    print("=" * 60)
    print("Тест: ui/notify.py")
    print("=" * 60)

    # Временный файл для notifications
    import config

    old_notify = config.NOTIFY_FILE
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".txt", mode="w")
    tmp.close()
    config.NOTIFY_FILE = tmp.name

    try:
        # notify_signal
        print("\nnotify_signal:")
        sig = make_signal()
        notify_signal(sig)

        # Проверяем, что файл существует и не пустой
        content = Path(tmp.name).read_text(encoding="utf-8")
        check("файл не пустой", len(content) > 0, True)
        check("содержит SHORT", "SHORT" in content, True)
        check("содержит breakout", "breakout" in content, True)
        check("содержит entry=12.500", "entry=12.500" in content, True)

        # Второй сигнал — дописывается
        print("\nвторой сигнал:")
        notify_signal(sig)
        content = Path(tmp.name).read_text(encoding="utf-8")
        lines = [l for l in content.strip().split("\n") if l]
        check("2 строки", len(lines), 2)

    finally:
        config.NOTIFY_FILE = old_notify
        Path(tmp.name).unlink(missing_ok=True)

    # Сводка
    print("\n" + "=" * 60)
    total = PASSED + FAILED
    print(f"Прoйдено: {PASSED} / {total}")
    if FAILED:
        sys.exit(1)
    else:
        print("✅ Все проверки пройдены")
        sys.exit(0)


if __name__ == "__main__":
    main()
