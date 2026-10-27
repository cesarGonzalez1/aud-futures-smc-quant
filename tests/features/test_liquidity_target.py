"""Tests de la salida jerárquica "próximo punto de liquidez" (ADR-011)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features import liquidity_target as lt


def _h1_base(n=10):
    idx = pd.date_range("2024-01-01 00:00", periods=n, freq="1h", tz="UTC")
    df = pd.DataFrame({
        schema.OPEN: [1.0] * n, schema.HIGH: [1.01] * n, schema.LOW: [0.99] * n, schema.CLOSE: [1.0] * n,
        "fvg_bull": [False] * n, "fvg_bear": [False] * n,
        "fvg_low": [np.nan] * n, "fvg_high": [np.nan] * n,
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    return df, idx


def test_unfilled_fvg_long_returns_far_edge():
    h1, idx = _h1_base()
    h1.loc[idx[3], ["fvg_bull", "fvg_low", "fvg_high"]] = [True, 1.10, 1.15]
    entry_time = idx[9] + pd.Timedelta(minutes=30)
    target = lt.next_unfilled_fvg_target(h1, entry_time, entry_price=1.00, side="long", lookback_bars=30)
    assert target == 1.15


def test_filled_fvg_is_discarded():
    h1, idx = _h1_base()
    h1.loc[idx[3], ["fvg_bull", "fvg_low", "fvg_high"]] = [True, 1.10, 1.15]
    h1.loc[idx[6], schema.CLOSE] = 1.12  # cierre posterior dentro de la zona -> rellenada
    entry_time = idx[9] + pd.Timedelta(minutes=30)
    target = lt.next_unfilled_fvg_target(h1, entry_time, entry_price=1.00, side="long", lookback_bars=30)
    assert target is None


def test_bearish_fvg_for_short_returns_low_edge():
    h1, idx = _h1_base()
    h1.loc[idx[3], ["fvg_bear", "fvg_low", "fvg_high"]] = [True, 0.85, 0.90]
    entry_time = idx[9] + pd.Timedelta(minutes=30)
    target = lt.next_unfilled_fvg_target(h1, entry_time, entry_price=1.00, side="short", lookback_bars=30)
    assert target == 0.85


def test_resolve_target_falls_back_to_day_range_when_ranging():
    h1, idx = _h1_base()
    entry_time = idx[9] + pd.Timedelta(minutes=30)
    row = pd.Series({"regime_vol": "baja", "day_hi": 1.20, "day_lo": 0.90,
                     "last_swing_high": 1.05, "last_swing_low": 0.80})
    target, source = lt.resolve_target(h1_fvg=h1, m5_row=row, entry_time=entry_time,
                                        entry_price=1.00, side="short")
    assert source == "day_range"
    assert target == 0.90


def test_resolve_target_falls_back_to_swing_when_not_ranging_and_no_fvg():
    h1, idx = _h1_base()
    entry_time = idx[9] + pd.Timedelta(minutes=30)
    row = pd.Series({"regime_vol": "alta", "day_hi": 1.20, "day_lo": 0.90,
                     "last_swing_high": 1.05, "last_swing_low": 0.80})
    target, source = lt.resolve_target(h1_fvg=h1, m5_row=row, entry_time=entry_time,
                                        entry_price=1.00, side="short")
    assert source == "swing_opposite"
    assert target == 0.80


def test_resolve_target_priority_fvg_beats_day_range():
    # Si hay una FVG util Y el dia viene oscilando, debe ganar la FVG (prioridad 1).
    h1, idx = _h1_base()
    h1.loc[idx[3], ["fvg_bear", "fvg_low", "fvg_high"]] = [True, 0.85, 0.90]
    entry_time = idx[9] + pd.Timedelta(minutes=30)
    row = pd.Series({"regime_vol": "baja", "day_hi": 1.20, "day_lo": 0.95,
                     "last_swing_high": 1.05, "last_swing_low": 0.80})
    target, source = lt.resolve_target(h1_fvg=h1, m5_row=row, entry_time=entry_time,
                                        entry_price=1.00, side="short")
    assert source == "fvg_h1"
    assert target == 0.85
