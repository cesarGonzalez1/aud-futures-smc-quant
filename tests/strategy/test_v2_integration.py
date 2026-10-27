"""Integración V2 (ADR-008): precondición de acumulación bloquea/permite el trade."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from strategy import liquidity_sweep_ifvg_v2 as v2


def _h1_bearish_with_acc(in_acc: bool):
    idx = pd.date_range("2024-01-02 00:00", periods=5, freq="1h", tz="UTC")
    df = pd.DataFrame({
        schema.OPEN:  [1.19, 1.19, 1.199, 1.18, 1.17],
        schema.HIGH:  [1.195, 1.198, 1.205, 1.19, 1.18],
        schema.LOW:   [1.185, 1.188, 1.195, 1.16, 1.15],
        schema.CLOSE: [1.19, 1.195, 1.198, 1.17, 1.16],
        "pdh": 1.20, "pdl": 1.05, "pwh": np.nan, "pwl": np.nan,
        "tokyo_hi": np.nan, "tokyo_lo": np.nan,
        "acc_high": np.nan, "acc_low": np.nan,
        "equal_high": False, "equal_low": False,
        "ob_bull_high": np.nan, "ob_bear_low": np.nan,
        "last_swing_high": 1.21, "last_swing_low": 1.10,
        "in_accumulation": in_acc,
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    return df


def _m5_bearish_ifvg():
    idx = pd.date_range("2024-01-02 03:00", periods=8, freq="5min", tz="UTC")
    n = len(idx)
    return pd.DataFrame({
        schema.OPEN:  [1.18, 1.178, 1.175, 1.17, 1.16, 1.14, 1.12, 1.10],
        schema.HIGH:  [1.182, 1.18, 1.176, 1.171, 1.161, 1.141, 1.121, 1.101],
        schema.LOW:   [1.176, 1.174, 1.169, 1.15, 1.13, 1.11, 1.095, 1.095],
        schema.CLOSE: [1.178, 1.175, 1.17, 1.16, 1.14, 1.12, 1.10, 1.098],
        "ifvg_bull": [False] * n,
        "ifvg_bear": [False, False, True, False, False, False, False, False],
    }, index=pd.DatetimeIndex(idx, name=schema.TIMESTAMP))


def test_v2_requires_accumulation():
    m5 = _m5_bearish_ifvg()
    bias = pd.Series({pd.Timestamp("2024-01-02", tz="UTC"): -1})

    # Sin acumulación => no opera, aunque haya sweep + IFVG válidos.
    no_acc = v2.generate_trades_v2(_h1_bearish_with_acc(False), m5, bias)
    assert no_acc == []

    # Con acumulación => genera la operación short (sweep de PDH alineado a bias).
    yes = v2.generate_trades_v2(_h1_bearish_with_acc(True), m5, bias)
    assert len(yes) == 1
    assert yes[0].side == "short"
    pois = v2.generate_trades_v2._last_pois
    assert "pdh" in pois[0]   # el POI barrido queda registrado


def test_v2_frame_has_poi_column():
    m5 = _m5_bearish_ifvg()
    bias = pd.Series({pd.Timestamp("2024-01-02", tz="UTC"): -1})
    trades = v2.generate_trades_v2(_h1_bearish_with_acc(True), m5, bias)
    df = v2.trades_to_frame(trades, v2.generate_trades_v2._last_pois)
    assert "poi" in df.columns
