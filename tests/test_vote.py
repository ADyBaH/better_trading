"""Тесты на indicators/vote.py: границы, веса, breakdown, None."""

import pytest

from indicators.vote import VoteResult, vote, vote_raw


class TestVoteRaw:
    def test_empty(self):
        r = vote_raw([])
        assert r.total == 0
        assert r.breakdown == {}
        assert r.label == ""

    def test_all_true(self):
        r = vote_raw([("a", True), ("b", True), ("c", True)])
        assert r.total == 3
        assert r.breakdown == {"a": 1, "b": 1, "c": 1}

    def test_all_false(self):
        r = vote_raw([("a", False), ("b", False)])
        assert r.total == -2
        assert r.breakdown == {"a": -1, "b": -1}

    def test_mixed(self):
        r = vote_raw([("a", True), ("b", False), ("c", True)])
        assert r.total == 1
        assert r.breakdown == {"a": 1, "b": -1, "c": 1}

    def test_none_abstain(self):
        r = vote_raw([("a", True), ("b", None), ("c", False)])
        assert r.total == 0
        assert r.breakdown == {"a": 1, "b": 0, "c": -1}

    def test_weights(self):
        r = vote_raw(
            [("a", True), ("b", True)],
            weights={"a": 2.0, "b": 0.5},
        )
        assert r.total == 2.5
        assert r.breakdown == {"a": 2.0, "b": 0.5}

    def test_weight_default_1(self):
        r = vote_raw([("a", True), ("b", True)], weights={"a": 3.0})
        assert r.total == 4.0  # 3.0 + 1.0

    def test_weight_negative_false(self):
        r = vote_raw([("a", False)], weights={"a": 2.0})
        assert r.total == -2.0


class TestVote:
    def test_no_thresholds_returns_raw(self):
        r = vote([("a", True), ("b", False)])
        assert r.total == 0
        assert r.label == ""

    def test_thresholds_main_trend_up(self):
        r = vote(
            [("a", True), ("b", True), ("c", None), ("d", None)],
            thresholds=[
                (">=", 3, "strong_up"),
                (">=", 2, "up"),
                ("<=", -2, "down"),
                ("<=", -3, "strong_down"),
            ],
            default="transition",
        )
        assert r.total == 2
        assert r.label == "up"

    def test_thresholds_main_trend_strong_up(self):
        r = vote(
            [("a", True), ("b", True), ("c", True), ("d", None)],
            thresholds=[
                (">=", 3, "strong_up"),
                (">=", 2, "up"),
                ("<=", -2, "down"),
                ("<=", -3, "strong_down"),
            ],
            default="transition",
        )
        assert r.total == 3
        assert r.label == "strong_up"

    def test_thresholds_main_trend_down(self):
        r = vote(
            [("a", False), ("b", False), ("c", None), ("d", None)],
            thresholds=[
                (">=", 3, "strong_up"),
                (">=", 2, "up"),
                ("<=", -2, "down"),
                ("<=", -3, "strong_down"),
            ],
            default="transition",
        )
        assert r.total == -2
        assert r.label == "down"

    def test_thresholds_main_trend_strong_down(self):
        r = vote(
            [("a", False), ("b", False), ("c", False), ("d", False)],
            thresholds=[
                (">=", 3, "strong_up"),
                (">=", 2, "up"),
                ("<=", -3, "strong_down"),
                ("<=", -2, "down"),
            ],
            default="transition",
        )
        assert r.total == -4
        assert r.label == "strong_down"

    def test_thresholds_transition(self):
        r = vote(
            [("a", True), ("b", False)],
            thresholds=[
                (">=", 3, "strong_up"),
                (">=", 2, "up"),
                ("<=", -2, "down"),
                ("<=", -3, "strong_down"),
            ],
            default="transition",
        )
        assert r.total == 0
        assert r.label == "transition"

    def test_thresholds_boundary_2(self):
        """total=2 → 'up' (не strong_up)."""
        r = vote(
            [("a", True), ("b", True)],
            thresholds=[(">=", 3, "strong_up"), (">=", 2, "up")],
            default="transition",
        )
        assert r.total == 2
        assert r.label == "up"

    def test_thresholds_boundary_3(self):
        """total=3 → 'strong_up'."""
        r = vote(
            [("a", True), ("b", True), ("c", True)],
            thresholds=[(">=", 3, "strong_up"), (">=", 2, "up")],
            default="transition",
        )
        assert r.total == 3
        assert r.label == "strong_up"

    def test_week_trend_neutral_zero(self):
        """total=0 → neutral (week_trend)."""
        r = vote(
            [("a", True), ("b", False)],
            thresholds=[
                (">=", 1, "bullish"),
                (">=", 0, "neutral"),
                ("<=", -1, "bearish"),
            ],
            default="bearish",
        )
        assert r.total == 0
        assert r.label == "neutral"

    def test_week_trend_bullish(self):
        r = vote(
            [("a", True), ("b", True), ("c", False)],
            thresholds=[
                (">=", 1, "bullish"),
                (">=", 0, "neutral"),
                ("<=", -1, "bearish"),
            ],
            default="bearish",
        )
        assert r.total == 1
        assert r.label == "bullish"

    def test_week_trend_bearish(self):
        r = vote(
            [("a", False), ("b", False), ("c", True)],
            thresholds=[
                (">=", 1, "bullish"),
                (">=", 0, "neutral"),
                ("<=", -1, "bearish"),
            ],
            default="bearish",
        )
        assert r.total == -1
        assert r.label == "bearish"
