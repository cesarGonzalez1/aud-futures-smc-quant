"""Integración V4 (ADR-010): igual que V3 pero el stop es el swing H1, no la mecha M5."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from strategy import liquidity_sweep_ifvg_v4 as v4


def _m5_bearish(h1_swing_high):
    idx = pd.date_range("2024-01-02 00:00", periods=9, freq="5min", tz="UTC")
    n = len(idx)
    df = pd.DataFrame({
        schema.OPEN:  [1.199, 1.18, 1.175, 1.17, 1.16, 1.14, 1.12, 1.10, 1.09],
        schema.HIGH:  [1.205, 1.182, 1.176, 1.171, 1.161, 1.141, 1.121, 1.101, 1.091],
        schema.LOW:   [1.195, 1.176, 1.169, 1.15, 1.13, 1.11, 1.095, 1.09, 1.085],
        schema.CLOSE: [1.198, 1.178, 1.175, 1.16, 1.14, 1.12, 1.10, 1.095, 1.088],
        "pdh": 1.20, "pdl": 1.05, "pwh": np.nan, "pwl": np.nan,
        "tokyo_hi": np.nan, "tokyo_lo": np.nan, "acc_high": np.nan, "acc_low": np.nan,
        "equal_high": False, "equal_low": False,
        "ob_bull_high": np.nan, "ob_bear_low": np.nan,
        "last_swing_high": 1.21, "last_swing_low": 1.10,
        "in_accumulation": True,
        "h1_swing_high": h1_swing_high, "h1_swing_low": 1.08,
        "ifvg_bull": [False] * n,
        "ifvg_bear": [False, False, True, False, False, False, False, False, False],
    }, index=pd.DatetimeIndex(idx, name=schema.TIMESTAMP))
    return df


def test_v4_stop_is_h1_swing_not_wick():
    bias = pd.Series({pd.Timestamp("2024-01-02", tz="UTC"): -1})
    # Swing H1 alto = 1.215 (más allá de la mecha M5 del sweep = 1.205).
    trades = v4.generate_trades_v4(_m5_bearish(1.215), bias, confirm_lookback=12)
    assert len(trades) == 1
    t = trades[0]
    assert t.side == "short"
    assert np.isclose(t.stop, 1.215)          # swing H1, NO la mecha (1.205)
    assert np.isclose(t.entry_price, 1.17)
    # Riesgo más amplio que con la mecha => menor sensibilidad al costo (punto de V4).
    assert (t.stop - t.entry_price) > (1.205 - t.entry_price)


def test_v4_skips_when_h1_swing_missing():
    bias = pd.Series({pd.Timestamp("2024-01-02", tz="UTC"): -1})
    # Sin swing H1 del lado correcto (NaN) => descarta, no cae a la mecha (ADR-010).
    assert v4.generate_trades_v4(_m5_bearish(np.nan), bias) == []
