import pytest

from decision_engine.risk_manager import (
    CircuitBreaker,
    position_size,
    score_adjusted_risk_pct,
)


def test_position_size_basic_fixed_fractional():
    result = position_size(
        account_equity=50_000, risk_pct=0.0075, entry_price=0.6550, stop_price=0.6500,
        contract_multiplier=100_000,
    )
    # riesgo permitido = 50000*0.0075=375; riesgo/contrato = 0.005*100000=500 -> 0 contratos
    assert result.contracts == 0
    assert result.risk_amount == pytest.approx(375.0)


def test_position_size_allows_at_least_one_contract_when_risk_fits():
    result = position_size(
        account_equity=50_000, risk_pct=0.02, entry_price=0.6550, stop_price=0.6500,
        contract_multiplier=100_000,
    )
    # riesgo permitido = 1000; riesgo/contrato = 500 -> 2 contratos
    assert result.contracts == 2


def test_position_size_respects_max_contracts_cap():
    result = position_size(
        account_equity=1_000_000, risk_pct=0.05, entry_price=0.6550, stop_price=0.6500,
        contract_multiplier=100_000, max_contracts=3,
    )
    assert result.contracts == 3
    assert result.capped_by_min_contract


def test_position_size_rejects_zero_risk_distance():
    with pytest.raises(ValueError):
        position_size(account_equity=50_000, risk_pct=0.01, entry_price=0.65, stop_price=0.65,
                       contract_multiplier=100_000)


def test_score_adjusted_risk_pct_scales_with_confidence():
    low = score_adjusted_risk_pct(-1.0)
    high = score_adjusted_risk_pct(0.5)
    mid = score_adjusted_risk_pct(-0.25)
    assert low < mid < high


def test_score_adjusted_risk_pct_clips_beyond_bounds():
    below = score_adjusted_risk_pct(-5.0)
    above = score_adjusted_risk_pct(5.0)
    assert below == score_adjusted_risk_pct(-1.0)
    assert above == score_adjusted_risk_pct(0.5)


def test_circuit_breaker_stops_after_max_consecutive_losses():
    cb = CircuitBreaker(max_consecutive_losses=2, max_trades_per_day=99)
    ok, _ = cb.can_trade()
    assert ok
    cb.register_trade(-1.0)
    ok, _ = cb.can_trade()
    assert ok
    cb.register_trade(-0.5)
    ok, reason = cb.can_trade()
    assert not ok
    assert "pérdidas consecutivas" in reason


def test_circuit_breaker_win_resets_consecutive_losses():
    cb = CircuitBreaker(max_consecutive_losses=2, max_trades_per_day=99)
    cb.register_trade(-1.0)
    cb.register_trade(0.8)
    assert cb.consecutive_losses == 0
    ok, _ = cb.can_trade()
    assert ok


def test_circuit_breaker_stops_at_daily_loss_limit():
    cb = CircuitBreaker(max_daily_loss_r=1.5, max_consecutive_losses=99, max_trades_per_day=99)
    cb.register_trade(-1.0)
    cb.register_trade(0.3)  # racha rota, pero el daily_r acumulado sigue negativo
    cb.register_trade(-1.0)
    ok, reason = cb.can_trade()
    assert not ok
    assert "límite diario" in reason


def test_circuit_breaker_reset_day_clears_daily_but_not_streak():
    cb = CircuitBreaker(max_consecutive_losses=5)
    cb.register_trade(-1.0)
    cb.register_trade(-1.0)
    cb.reset_day()
    assert cb.daily_r == 0.0
    assert cb.trades_today == 0
    assert cb.consecutive_losses == 2  # la racha NO se resetea al cambiar de dia
