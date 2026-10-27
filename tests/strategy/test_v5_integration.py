"""Test de integración end-to-end de la hipótesis V5 (ADR-011)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from strategy import liquidity_sweep_ifvg_v5 as v5


def test_v5_generates_long_trade_with_full_pipeline():
    idx = pd.date_range("2024-01-02 00:00", periods=20, freq="5min", tz="UTC")
    n = len(idx)
    m5 = pd.DataFrame({
        schema.OPEN: [1.00] * n, schema.HIGH: [1.001] * n, schema.LOW: [0.999] * n, schema.CLOSE: [1.00] * n,
        "equal_low_recent": [False] * n, "equal_high_recent": [False] * n,
        "liquidity_sweep_low": [False] * n, "liquidity_sweep_high": [False] * n,
        "ifvg_bull": [False] * n, "ifvg_bear": [False] * n,
        "h1_swing_high": [1.05] * n, "h1_swing_low": [0.90] * n,
        "last_swing_high": [1.03] * n, "last_swing_low": [0.95] * n,
        "regime_vol": ["alta"] * n, "day_hi": [1.02] * n, "day_lo": [0.92] * n,
    }, index=idx)
    m5.index.name = schema.TIMESTAMP
    m5.loc[idx[2], ["equal_low_recent", "liquidity_sweep_low"]] = [True, True]
    m5.loc[idx[5], "ifvg_bull"] = True

    h1 = pd.DataFrame({
        schema.OPEN: [1.0] * 5, schema.HIGH: [1.01] * 5, schema.LOW: [0.99] * 5, schema.CLOSE: [1.0] * 5,
        "fvg_bull": [False] * 5, "fvg_bear": [False] * 5,
        "fvg_low": [np.nan] * 5, "fvg_high": [np.nan] * 5,
    }, index=pd.date_range("2024-01-01 20:00", periods=5, freq="1h", tz="UTC"))
    h1.index.name = schema.TIMESTAMP

    confluence = pd.DataFrame({"direction": [1], "confidence": ["alta"]},
                              index=[pd.Timestamp("2024-01-02", tz="UTC")])

    trades, confidences, sources = v5.generate_trades_v5(m5, h1, confluence, confirm_lookback=12)

    assert len(trades) == 1
    t = trades[0]
    assert t.side == "long"
    assert t.stop == 0.90       # h1_swing_low
    assert confidences[0] == "alta"
    assert sources[0] in ("day_range", "swing_opposite")

    df = v5.trades_to_frame(trades, confidences, sources)
    assert {"confidence", "target_source"}.issubset(df.columns)


def test_v5_no_trade_without_confluence_direction():
    idx = pd.date_range("2024-01-02 00:00", periods=10, freq="5min", tz="UTC")
    n = len(idx)
    m5 = pd.DataFrame({
        schema.OPEN: [1.00] * n, schema.HIGH: [1.001] * n, schema.LOW: [0.999] * n, schema.CLOSE: [1.00] * n,
        "equal_low_recent": [True] * n, "liquidity_sweep_low": [True] * n,
        "ifvg_bull": [True] * n, "ifvg_bear": [False] * n, "equal_high_recent": [False] * n,
        "liquidity_sweep_high": [False] * n,
        "h1_swing_high": [1.05] * n, "h1_swing_low": [0.90] * n,
        "last_swing_high": [1.03] * n, "last_swing_low": [0.95] * n,
        "regime_vol": ["alta"] * n, "day_hi": [1.02] * n, "day_lo": [0.92] * n,
    }, index=idx)
    m5.index.name = schema.TIMESTAMP
    h1 = pd.DataFrame({
        schema.OPEN: [1.0] * 3, schema.HIGH: [1.01] * 3, schema.LOW: [0.99] * 3, schema.CLOSE: [1.0] * 3,
        "fvg_bull": [False] * 3, "fvg_bear": [False] * 3,
        "fvg_low": [np.nan] * 3, "fvg_high": [np.nan] * 3,
    }, index=pd.date_range("2024-01-01 20:00", periods=3, freq="1h", tz="UTC"))
    h1.index.name = schema.TIMESTAMP
    # direction=0 -> no debe operar aunque el resto de condiciones se cumplan.
    confluence = pd.DataFrame({"direction": [0], "confidence": ["na"]},
                              index=[pd.Timestamp("2024-01-02", tz="UTC")])
    trades, _, _ = v5.generate_trades_v5(m5, h1, confluence)
    assert len(trades) == 0
