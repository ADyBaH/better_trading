"""Тесты на ui/notify.py."""

from pathlib import Path

import pytest

import config
from core.models import Signal
from ui.notify import notify_signal


@pytest.fixture
def make_signal():
    def _make():
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

    return _make


@pytest.fixture
def notify_file(tmp_path, monkeypatch):
    """Подменяет config.NOTIFY_FILE на tmp_path/notifications.txt."""
    path = tmp_path / "notifications.txt"
    monkeypatch.setattr(config, "NOTIFY_FILE", str(path))
    return path


class TestNotifySignal:
    def test_file_not_empty(self, make_signal, notify_file):
        notify_signal(make_signal())
        content = notify_file.read_text(encoding="utf-8")
        assert len(content) > 0

    def test_contains_short(self, make_signal, notify_file):
        notify_signal(make_signal())
        content = notify_file.read_text(encoding="utf-8")
        assert "SHORT" in content

    def test_contains_breakout(self, make_signal, notify_file):
        notify_signal(make_signal())
        content = notify_file.read_text(encoding="utf-8")
        assert "breakout" in content

    def test_contains_entry(self, make_signal, notify_file):
        notify_signal(make_signal())
        content = notify_file.read_text(encoding="utf-8")
        assert "entry=12.500" in content

    def test_two_signals_two_lines(self, make_signal, notify_file):
        notify_signal(make_signal())
        notify_signal(make_signal())
        content = notify_file.read_text(encoding="utf-8")
        lines = [l for l in content.strip().split("\n") if l]
        assert len(lines) == 2
