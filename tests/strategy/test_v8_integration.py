"""Test de integración de V8 (ADR-015): único cambio frente a V7 es el stop
(swing M5 en vez de swing H1)."""

from __future__ import annotations

import pandas as pd

from data import schema
from strategy.liquidity_sweep_ifvg_v8 import generate_trades_v8


def _base_m5(n: int = 40) -> pd.DataFrame:
    idx = pd.date_range("2024-01-02 00:00", periods=n, freq="5min", tz="UTC")
    df = pd.DataFrame({
        schema.OPEN: [1.00] * n, schema.HIGH: [1.02] * n, schema.LOW: [0.98] * n, schema.CLOSE: [1.00] * n,
        "equal_high_recent": [False] * n, "liquidity_sweep_high": [False] * n,
        "equal_low_recent": [False] * n, "liquidity_sweep_low": [False] * n,
        "mss_bull": [False] * n, "mss_bear": [False] * n,
        "ifvg_bull": [False] * n, "ifvg_bear": [False] * n,
        "h1_swing_high": [1.10] * n, "h1_swing_low": [0.90] * n,   # NO debe usarse en V8
        "last_swing_high": [1.05] * n, "last_swing_low": [0.95] * n,  # swing M5, SÍ debe usarse
        "regime_vol": ["alta"] * n, "day_hi": [1.20] * n, "day_lo": [0.80] * n,
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    return df


def _empty_h1() -> pd.DataFrame:
    return pd.DataFrame(index=pd.DatetimeIndex([], tz="UTC", name=schema.TIMESTAMP))


def test_v8_stop_uses_m5_swing_not_h1_swing():
    m5 = _base_m5()
    idx = m5.index

    m5.loc[idx[0], "equal_high_recent"] = True
    m5.loc[idx[0], "liquidity_sweep_high"] = True
    m5.loc[idx[0], schema.OPEN] = 1.00  # referencia para CISD

    m5.loc[idx[5], schema.CLOSE] = 0.99  # confirma CISD (mss_bear queda False)

    m5.loc[idx[10], "ifvg_bear"] = True
    m5.loc[idx[11], schema.OPEN] = 0.6543  # precio de entrada

    confluence = pd.DataFrame(
        {"direction": [-1], "confidence": ["alta"]},
        index=pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")]),
    )

    trades, *_rest = generate_trades_v8(m5, _empty_h1(), confluence)

    assert len(trades) == 1
    t = trades[0]
    assert t.stop == 1.05    # swing M5 (last_swing_high), NO 1.10 (h1_swing_high)
    assert t.target == 0.6525  # jerarquía de target idéntica a V7 (Quarter Theory)


def test_v8_rejects_stop_too_close_to_entry_per_atr_filter():
    m5 = _base_m5()
    idx = m5.index
    m5["atr"] = 1.0  # ATR grande -> el stop (last_swing_high=1.05 vs entry~1.00) queda por debajo del piso

    m5.loc[idx[0], "equal_high_recent"] = True
    m5.loc[idx[0], "liquidity_sweep_high"] = True
    m5.loc[idx[0], schema.OPEN] = 1.00
    m5.loc[idx[5], schema.CLOSE] = 0.99
    m5.loc[idx[10], "ifvg_bear"] = True
    m5.loc[idx[11], schema.OPEN] = 1.00  # entrada cerca del swing -> riesgo pequeño frente a ATR=1.0

    confluence = pd.DataFrame(
        {"direction": [-1], "confidence": ["alta"]},
        index=pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")]),
    )

    trades, *_rest = generate_trades_v8(m5, _empty_h1(), confluence, min_stop_atr_frac=0.3)
    assert len(trades) == 0  # riesgo (~0.05) < 0.3*ATR (0.3) -> se descarta
