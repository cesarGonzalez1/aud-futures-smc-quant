"""Test de integración de decision_engine.live_signal (ADR-017)."""

from __future__ import annotations

import pandas as pd

from data import schema
from decision_engine.live_signal import evaluate_latest
from decision_engine.scoring import ConfluenceScorer


def _base_m5(n: int = 40) -> pd.DataFrame:
    idx = pd.date_range("2024-01-02 00:00", periods=n, freq="5min", tz="UTC")
    df = pd.DataFrame({
        schema.OPEN: [1.00] * n, schema.HIGH: [1.02] * n, schema.LOW: [0.98] * n, schema.CLOSE: [1.00] * n,
        "equal_high_recent": [False] * n, "liquidity_sweep_high": [False] * n,
        "equal_low_recent": [False] * n, "liquidity_sweep_low": [False] * n,
        "mss_bull": [False] * n, "mss_bear": [False] * n,
        "ifvg_bull": [False] * n, "ifvg_bear": [False] * n,
        "h1_swing_high": [1.10] * n, "h1_swing_low": [0.90] * n,
        "last_swing_high": [1.10] * n, "last_swing_low": [0.90] * n,
        "regime_vol": ["alta"] * n, "day_hi": [1.20] * n, "day_lo": [0.80] * n,
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    return df


def _empty_h1() -> pd.DataFrame:
    return pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC", name=schema.TIMESTAMP))


def _fake_scorer() -> ConfluenceScorer:
    train = pd.DataFrame({
        "confidence": ["alta", "baja"], "confirmation_source": ["mss", "mss"],
        "quarter_aligned": [True, False], "target_source": ["quarter_level", "fvg_h1"],
        "side": ["short", "long"], "r_net": [-0.3, 0.2],
    })
    return ConfluenceScorer.fit(train)


def _mss_setup(m5: pd.DataFrame) -> pd.DataFrame:
    idx = m5.index
    m5 = m5.copy()
    m5.loc[idx[0], "equal_high_recent"] = True
    m5.loc[idx[0], "liquidity_sweep_high"] = True
    m5.loc[idx[5], "mss_bear"] = True
    m5.loc[idx[10], "ifvg_bear"] = True
    m5.loc[idx[11], schema.OPEN] = 0.6543
    return m5


def test_evaluate_latest_returns_signal_when_recent():
    m5 = _mss_setup(_base_m5())
    confluence = pd.DataFrame(
        {"direction": [-1], "confidence": ["alta"]},
        index=pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")]),
    )
    entry_time = m5.index[11]
    signal = evaluate_latest(
        m5, _empty_h1(), confluence, _fake_scorer(),
        as_of=entry_time + pd.Timedelta(hours=1), lookback_hours=6,
    )
    assert signal.has_signal
    assert signal.side == "short"
    assert signal.score is not None
    assert "vigente" in signal.reason


def test_evaluate_latest_no_signal_when_too_old():
    m5 = _mss_setup(_base_m5())
    confluence = pd.DataFrame(
        {"direction": [-1], "confidence": ["alta"]},
        index=pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")]),
    )
    entry_time = m5.index[11]
    signal = evaluate_latest(
        m5, _empty_h1(), confluence, _fake_scorer(),
        as_of=entry_time + pd.Timedelta(hours=48), lookback_hours=6,
    )
    assert not signal.has_signal
    assert "fuera de la ventana" in signal.reason


def test_evaluate_latest_no_signal_when_no_setup_at_all():
    m5 = _base_m5()  # sin sweep/MSS/IFVG -> nunca genera trade
    confluence = pd.DataFrame(
        {"direction": [-1], "confidence": ["alta"]},
        index=pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")]),
    )
    signal = evaluate_latest(m5, _empty_h1(), confluence, _fake_scorer())
    assert not signal.has_signal
    assert "ninguna señal" in signal.reason


def test_signal_summary_formats_both_cases():
    sig_no = evaluate_latest(_base_m5(), _empty_h1(),
                              pd.DataFrame({"direction": [0], "confidence": ["na"]},
                                           index=pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")])),
                              _fake_scorer())
    assert "NO-TRADE" in sig_no.summary()


def test_evaluate_latest_with_position_sizing():
    m5 = _mss_setup(_base_m5())
    confluence = pd.DataFrame(
        {"direction": [-1], "confidence": ["alta"]},
        index=pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")]),
    )
    entry_time = m5.index[11]
    signal = evaluate_latest(
        m5, _empty_h1(), confluence, _fake_scorer(),
        as_of=entry_time + pd.Timedelta(hours=1), lookback_hours=6,
        account_equity=50_000, contract_multiplier=100_000,
    )
    assert signal.has_signal
    assert signal.suggested_contracts is not None
    assert signal.risk_pct_used is not None
    assert signal.circuit_breaker_ok


def test_evaluate_latest_respects_active_circuit_breaker():
    from decision_engine.risk_manager import CircuitBreaker

    m5 = _mss_setup(_base_m5())
    confluence = pd.DataFrame(
        {"direction": [-1], "confidence": ["alta"]},
        index=pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")]),
    )
    entry_time = m5.index[11]
    cb = CircuitBreaker(max_consecutive_losses=2, max_trades_per_day=99)
    cb.register_trade(-1.0)
    cb.register_trade(-1.0)  # 2 perdidas seguidas -> freno activo

    signal = evaluate_latest(
        m5, _empty_h1(), confluence, _fake_scorer(),
        as_of=entry_time + pd.Timedelta(hours=1), lookback_hours=6,
        circuit_breaker=cb,
    )
    assert signal.has_signal  # la senal SI existe...
    assert not signal.circuit_breaker_ok  # ...pero el freno dice que no se opera
    assert "FRENO" in signal.summary()
