"""
Тесты на compute_trade_result и Instrument.
"""

import pytest

from core.instruments import Instrument, compute_trade_result, get_instrument


@pytest.fixture
def inst_cnyrubf():
    return get_instrument("CNYRUBF")


class TestComputeTradeResult:
    def test_long_loss_exact_rub(self, inst_cnyrubf):
        # 12.500 → 12.470 = −30 pts, rub = −30 − 2.06 = −32.06
        points, rub = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.470)
        assert points == -30.0
        assert rub == pytest.approx(-32.06, rel=1e-2)

    def test_short_win_exact_rub(self, inst_cnyrubf):
        # 12.530 → 12.500 = +30 pts, rub = 27.94
        points, rub = compute_trade_result(inst_cnyrubf, "short", 12.530, 12.500)
        assert points == 30.0
        assert rub == pytest.approx(27.94, rel=1e-2)

    def test_short_loss_exact_rub(self, inst_cnyrubf):
        points, rub = compute_trade_result(inst_cnyrubf, "short", 12.500, 12.530)
        assert points == -30.0
        assert rub == pytest.approx(-32.06, rel=1e-2)

    def test_size_2(self, inst_cnyrubf):
        # points не зависит от size, rub × 2, комиссия × 2
        points, rub = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.530, size=2)
        assert points == 30.0
        assert rub == pytest.approx(55.88, rel=1e-2)

    def test_override_commission(self, inst_cnyrubf):
        # commission_round=1.5 → rub = 30 − 1.5 = 28.5
        points, rub = compute_trade_result(
            inst_cnyrubf, "long", 12.500, 12.530, commission_round=1.5
        )
        assert rub == pytest.approx(28.5, rel=1e-2)

    def test_long_profit(self, inst_cnyrubf):
        points, rub = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.530)
        assert points == 30.0
        assert rub == pytest.approx(27.94, rel=1e-2)

    def test_long_loss(self, inst_cnyrubf):
        points, rub = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.470)
        assert points == -30.0
        assert rub < 0

    def test_short_profit(self, inst_cnyrubf):
        points, rub = compute_trade_result(inst_cnyrubf, "short", 12.500, 12.470)
        assert points == 30.0
        assert rub == pytest.approx(27.94, rel=1e-2)

    def test_short_loss(self, inst_cnyrubf):
        points, rub = compute_trade_result(inst_cnyrubf, "short", 12.500, 12.530)
        assert points == -30.0
        assert rub < 0

    def test_zero_result(self, inst_cnyrubf):
        points, rub = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.500)
        assert points == 0.0
        assert rub == pytest.approx(-2.06, rel=1e-2)

    def test_commission_deducted(self, inst_cnyrubf):
        # 30 пунктов = 30 ₽ gross - 2.06 комиссия = 27.94
        _, rub = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.530)
        assert rub == pytest.approx(27.94, rel=1e-2)


class TestGetInstrument:
    def test_get_cnyrubf(self):
        inst = get_instrument("CNYRUBF")
        assert inst.symbol == "CNYRUBF"
        assert inst.price_step == 0.001
        assert inst.step_cost == 1.0
        assert inst.lot_size == 1000

    def test_commission_round(self):
        inst = get_instrument("CNYRUBF")
        # 0.58 + 0.45 = 1.03? или 2.06 (круг)?
        # По ROADMAP: 0.58 (MOEX) + 0.45 (Финам) = 2.06 (круг)
        assert inst.commission_round == pytest.approx(2.06, rel=1e-2)

    def test_unknown_symbol_raises(self):
        with pytest.raises(ValueError):
            get_instrument("UNKNOWN")

    def test_instrument_is_dataclass(self):
        inst = get_instrument("CNYRUBF")
        assert hasattr(inst, "symbol")
        assert hasattr(inst, "price_step")
        assert hasattr(inst, "step_cost")
        assert hasattr(inst, "commission_round")

    def test_list_instruments(self):
        """list_instruments() возвращает все тикеры из INSTRUMENTS."""
        from core.instruments import list_instruments

        symbols = list_instruments()
        assert isinstance(symbols, list)
        assert "CNYRUBF" in symbols
        assert len(symbols) == len(INSTRUMENTS)


class TestEdgeCases:
    def test_empty_direction_raises(self):
        inst = get_instrument("CNYRUBF")
        with pytest.raises((ValueError, KeyError)):
            compute_trade_result(inst, "wrong", 12.5, 12.6)

    def test_round_result(self):
        # points / rub должны быть округлены до 1 / 2 знаков
        inst = get_instrument("CNYRUBF")
        points, rub = compute_trade_result(inst, "long", 12.500, 12.5301)
        assert isinstance(points, float)
        assert isinstance(rub, float)
        # points округлён до 1 знака
        assert points == round(points, 1)


# ============================================================
# T-19: консистентность спецификаций
# ============================================================


from core.instruments import INSTRUMENTS


class TestSpecsConsistent:
    """T-19: для каждого Instrument в INSTRUMENTS — проверка консистентности."""

    @pytest.mark.parametrize("symbol", list(INSTRUMENTS.keys()))
    def test_step_cost_formula(self, symbol):
        """step_cost == price_step * lot_size * multiplier (multiplier=1 для CNYRUBF).

        CNYRUBF: 0.001 × 1000 × 1 = 1.0 ₽.
        Для других инструментов multiplier может быть != 1,
        но формула должна сходиться.
        """
        inst = INSTRUMENTS[symbol]
        expected = inst.price_step * inst.lot_size
        assert inst.step_cost == pytest.approx(expected, rel=1e-9), (
            f"{symbol}: step_cost={inst.step_cost}, " f"price_step×lot_size={expected}"
        )

    @pytest.mark.parametrize("symbol", list(INSTRUMENTS.keys()))
    def test_commission_round_is_sum(self, symbol):
        """commission_round == commission_open + commission_close."""
        inst = INSTRUMENTS[symbol]
        assert inst.commission_round == pytest.approx(
            inst.commission_open + inst.commission_close, rel=1e-9
        )

    @pytest.mark.parametrize("symbol", list(INSTRUMENTS.keys()))
    def test_commission_open_close_symmetric(self, symbol):
        """commission_open == commission_close (биржа + брокер симметричны)."""
        inst = INSTRUMENTS[symbol]
        assert inst.commission_open == pytest.approx(inst.commission_close, rel=1e-9)

    @pytest.mark.parametrize("symbol", list(INSTRUMENTS.keys()))
    def test_commission_round_positive(self, symbol):
        inst = INSTRUMENTS[symbol]
        assert inst.commission_round > 0

    @pytest.mark.parametrize("symbol", list(INSTRUMENTS.keys()))
    def test_price_step_positive(self, symbol):
        inst = INSTRUMENTS[symbol]
        assert inst.price_step > 0
        assert inst.lot_size > 0
        assert inst.step_cost > 0

    @pytest.mark.parametrize("symbol", list(INSTRUMENTS.keys()))
    def test_symbol_matches_key(self, symbol):
        """inst.symbol == ключ в INSTRUMENTS."""
        inst = INSTRUMENTS[symbol]
        assert inst.symbol == symbol


class TestComputeTradeResultScaling:
    """T-19: compute_trade_result масштабируется линейно по size и step_cost."""

    def test_linear_in_size_points(self, inst_cnyrubf):
        """points не зависит от size (это пункты, не рубли)."""
        p1, _ = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.530, size=1)
        p2, _ = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.530, size=2)
        p3, _ = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.530, size=5)
        assert p1 == p2 == p3 == 30.0

    def test_linear_in_size_rub(self, inst_cnyrubf):
        """rub × size (при тех же points)."""
        _, r1 = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.530, size=1)
        _, r2 = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.530, size=2)
        _, r3 = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.530, size=3)
        assert r2 == pytest.approx(r1 * 2, rel=1e-9)
        assert r3 == pytest.approx(r1 * 3, rel=1e-9)

    def test_size_zero(self, inst_cnyrubf):
        """size=0 → 0 points, 0 rub (комиссия тоже 0)."""
        points, rub = compute_trade_result(inst_cnyrubf, "long", 12.500, 12.530, size=0)
        assert points == 30.0  # points не зависит от size
        assert rub == 0.0  # rub = 30 × 1.0 × 0 − 2.06 × 0 = 0

    def test_commission_scales_with_size(self, inst_cnyrubf):
        """T-19: комиссия × size (Вариант A).

        gross_rub = points × step_cost × size
        rub = gross_rub − commission_round × size
        Значит, rub(size=N) = N × points × step_cost − N × commission_round
        """
        points = 30.0
        step_cost = inst_cnyrubf.step_cost  # 1.0
        comm = inst_cnyrubf.commission_round  # 2.06

        for size in (1, 2, 3, 5):
            _, rub = compute_trade_result(
                inst_cnyrubf, "long", 12.500, 12.530, size=size
            )
            expected = points * step_cost * size - comm * size
            assert rub == pytest.approx(
                expected, rel=1e-2
            ), f"size={size}: rub={rub}, expected={expected}"

    def test_commission_override_scales_with_size(self, inst_cnyrubf):
        """commission_round=1.5, size=2 → rub = 60 − 3 = 57."""
        points, rub = compute_trade_result(
            inst_cnyrubf, "long", 12.500, 12.530, size=2, commission_round=1.5
        )
        assert points == 30.0
        assert rub == pytest.approx(57.0, rel=1e-9)
