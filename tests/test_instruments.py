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
