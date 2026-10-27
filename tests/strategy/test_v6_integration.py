"""Test de integración de V6 (ADR-014): señal de V1 + stop de swing H1."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from strategy.liquidity_sweep_ifvg_v6 import generate_trades_v6


def test_v6_uses_h1_swing_as_stop_not_the_sweep_candle_wick():
    idx_h1 = pd.date_range("2024-01-02 00:00", periods=3, freq="1h", tz="UTC")
    h1 = pd.DataFrame({
        schema.HIGH: [1.05, 1.06, 1.02], schema.LOW: [1.00, 1.00, 0.98], schema.CLOSE: [1.00, 0.99, 0.99],
        "pdh": [1.05] * 3, "pdl": [np.nan] * 3, "tokyo_hi": [np.nan] * 3, "tokyo_lo": [np.nan] * 3,
        "last_swing_high": [1.10] * 3, "last_swing_low": [0.90] * 3,
    }, index=idx_h1)
    h1.index.name = schema.TIMESTAMP

    idx_m5 = pd.date_range("2024-01-02 01:00", periods=15, freq="5min", tz="UTC")
    m5 = pd.DataFrame({
        schema.OPEN: [1.0] * 15, schema.HIGH: [1.0] * 15, schema.LOW: [1.0] * 15, schema.CLOSE: [1.0] * 15,
        "ifvg_bear": [False] * 15, "ifvg_bull": [False] * 15,
    }, index=idx_m5)
    m5.index.name = schema.TIMESTAMP
    m5.loc[idx_m5[12], "ifvg_bear"] = True  # dentro de la ventana de confirmación [02:00,03:00)

    daily_bias = pd.Series({pd.Timestamp("2024-01-02", tz="UTC"): -1})

    trades = generate_trades_v6(h1, m5, daily_bias)

    assert len(trades) == 1
    t = trades[0]
    assert t.side == "short"
    assert t.stop == 1.10   # swing H1, NO la mecha del sweep (1.06)
    assert t.target == 0.90


def test_v6_no_trade_when_h1_swing_missing():
    idx_h1 = pd.date_range("2024-01-02 00:00", periods=3, freq="1h", tz="UTC")
    h1 = pd.DataFrame({
        schema.HIGH: [1.05, 1.06, 1.02], schema.LOW: [1.00, 1.00, 0.98], schema.CLOSE: [1.00, 0.99, 0.99],
        "pdh": [1.05] * 3, "pdl": [np.nan] * 3, "tokyo_hi": [np.nan] * 3, "tokyo_lo": [np.nan] * 3,
        "last_swing_high": [np.nan] * 3, "last_swing_low": [0.90] * 3,  # sin swing high -> sin stop valido
    }, index=idx_h1)
    h1.index.name = schema.TIMESTAMP

    idx_m5 = pd.date_range("2024-01-02 01:00", periods=15, freq="5min", tz="UTC")
    m5 = pd.DataFrame({
        schema.OPEN: [1.0] * 15, schema.HIGH: [1.0] * 15, schema.LOW: [1.0] * 15, schema.CLOSE: [1.0] * 15,
        "ifvg_bear": [False] * 15, "ifvg_bull": [False] * 15,
    }, index=idx_m5)
    m5.index.name = schema.TIMESTAMP
    m5.loc[idx_m5[12], "ifvg_bear"] = True

    daily_bias = pd.Series({pd.Timestamp("2024-01-02", tz="UTC"): -1})
    trades = generate_trades_v6(h1, m5, daily_bias)
    assert len(trades) == 0
