"""Tests de FVG / Inverse FVG sobre datos sintéticos conocidos (ADR-007 anexo)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features import fvg


def _frame(rows) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(rows), freq="5min", tz="UTC")
    df = pd.DataFrame(rows, columns=[schema.OPEN, schema.HIGH, schema.LOW, schema.CLOSE], index=idx)
    df.index.name = schema.TIMESTAMP
    df["atr"] = 0.0  # sin filtro de tamaño en estos tests
    return df


def test_bullish_fvg_detected_on_third_candle():
    # vela0 high=10; vela1 sube; vela2 low=11 > high[0]=10 -> FVG alcista en índice 2.
    rows = [
        [9, 10, 8, 9],     # t-2: high=10
        [10, 13, 10, 12],  # t-1
        [12, 14, 11, 13],  # t: low=11 > 10 -> gap [10,11]
    ]
    out = fvg.detect_fvg(_frame(rows), min_atr_frac=0.0)
    assert out["fvg_bull"].iloc[2]
    assert out["fvg_low"].iloc[2] == 10 and out["fvg_high"].iloc[2] == 11


def test_bearish_fvg_detected():
    rows = [
        [12, 13, 11, 12],  # t-2: low=11
        [11, 11, 8, 9],
        [9, 10, 7, 8],     # t: high=10 < low[t-2]=11 -> gap [10,11]
    ]
    out = fvg.detect_fvg(_frame(rows), min_atr_frac=0.0)
    assert out["fvg_bear"].iloc[2]
    assert out["fvg_low"].iloc[2] == 10 and out["fvg_high"].iloc[2] == 11


def test_size_filter_rejects_small_gap():
    rows = [[9, 10, 8, 9], [10, 13, 10, 12], [12, 14, 10.05, 13]]  # gap 0.05
    df = _frame(rows)
    df["atr"] = 1.0  # min gap = 0.1*1 = 0.1 > 0.05 -> rechazado
    out = fvg.detect_fvg(df, min_atr_frac=0.1)
    assert not out["fvg_bull"].iloc[2]


def test_inverse_fvg_confirmation():
    # FVG alcista en índice 2 (zona [10,11]); luego un cierre < 10 -> IFVG bajista.
    rows = [
        [9, 10, 8, 9],
        [10, 13, 10, 12],
        [12, 14, 11, 13],   # FVG alcista, low zona=10
        [13, 13, 12, 12.5],
        [12, 12, 9, 9.5],   # cierra 9.5 < 10 -> invalida FVG alcista -> IFVG bajista
    ]
    out = fvg.add_fvg_features(_frame(rows), min_atr_frac=0.0)
    assert out["fvg_bull"].iloc[2]
    assert out["ifvg_bear"].iloc[4]
    assert not out["ifvg_bear"].iloc[3]
