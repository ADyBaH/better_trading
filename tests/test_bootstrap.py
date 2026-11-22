"""T-04: Bootstrap CI для paper_stats."""

import pytest

from trader.bootstrap import (
    _bootstrap_ci,
    _pf_from_points,
    _exp_from_points,
    _winrate_from_points,
)


class TestBootstrapCI:
    def test_empty(self):
        assert _bootstrap_ci([], _exp_from_points) is None

    def test_single_value(self):
        ci = _bootstrap_ci([1.0], _exp_from_points)
        assert ci == (1.0, 1.0)

    def test_symmetric_distribution(self):
        # Симметричное распределение вокруг 0 → CI включает 0
        values = [-1.0, -0.5, 0.0, 0.5, 1.0] * 20  # n=100
        ci = _bootstrap_ci(values, _exp_from_points)
        assert ci is not None
        lo, hi = ci
        assert lo <= 0.0 <= hi

    def test_coverage_95(self):
        """Coverage ≈ 95% на 100 выборках N(0,1) с n=50."""
        import random

        rng = random.Random(42)
        true_mean = 0.0
        covered = 0
        n_tests = 100

        for _ in range(n_tests):
            sample = [rng.gauss(0, 1) for _ in range(50)]
            ci = _bootstrap_ci(sample, _exp_from_points, n_iter=200)
            if ci and ci[0] <= true_mean <= ci[1]:
                covered += 1

        coverage = covered / n_tests
        assert 0.85 <= coverage <= 1.0, f"coverage={coverage}, ожидалось ~0.95"

    def test_pf_ci(self):
        # 3 win, 2 loss
        values = [10.0, 20.0, 30.0, -10.0, -20.0]
        ci = _bootstrap_ci(values, _pf_from_points)
        assert ci is not None
        lo, hi = ci
        assert lo <= 3.0 <= hi  # PF = (10+20+30)/30 = 2.0 → CI около 2

    def test_winrate_ci(self):
        values = [10.0, -10.0, 10.0, -10.0, 10.0]  # 3W / 2L → 60%
        ci = _bootstrap_ci(values, _winrate_from_points)
        assert ci is not None
        lo, hi = ci
        assert lo <= 60.0 <= hi
