"""Tests de PDH/PDL y niveles de sesión Tokio, con foco anti-look-ahead (ADR-007)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features import levels


def _d1(days, highs, lows) -> pd.DataFrame:
    idx = pd.DatetimeIndex(pd.to_datetime(days), name=schema.TIMESTAMP).tz_localize("UTC")
    df = pd.DataFrame({schema.OPEN: lows, schema.HIGH: highs, schema.LOW: lows,
                       schema.CLOSE: highs}, index=idx)
    return df


def test_pdh_pdl_uses_previous_day_only():
    d1 = _d1(["2024-01-01", "2024-01-02", "2024-01-03"], [1.1, 1.2, 1.3], [1.0, 1.05, 1.1])
    idx = pd.date_range("2024-01-02 00:00", "2024-01-02 23:00", freq="1h", tz="UTC")
    intr = pd.DataFrame({schema.OPEN: 1.15, schema.HIGH: 1.25, schema.LOW: 1.12,
                         schema.CLOSE: 1.18}, index=idx)
    intr.index.name = schema.TIMESTAMP
    out = levels.add_pdh_pdl(intr, d1)
    # Día 2024-01-02 => PDH/PDL del 2024-01-01 (1.1 / 1.0), NUNCA del día en curso.
    assert (out["pdh"] == 1.1).all()
    assert (out["pdl"] == 1.0).all()


def test_pdh_anti_lookahead_ignores_current_day_extreme():
    # El high del día en curso (1.25 intradía) no debe aparecer como PDH ese día.
    d1 = _d1(["2024-01-01", "2024-01-02"], [1.1, 9.9], [1.0, 0.1])
    idx = pd.date_range("2024-01-02 00:00", periods=3, freq="1h", tz="UTC")
    intr = pd.DataFrame({schema.OPEN: 1.15, schema.HIGH: 1.25, schema.LOW: 1.12,
                         schema.CLOSE: 1.18}, index=idx)
    intr.index.name = schema.TIMESTAMP
    out = levels.add_pdh_pdl(intr, d1)
    assert (out["pdh"] == 1.1).all()   # no 9.9 (día en curso)


def test_tokyo_session_levels_expanding():
    idx = pd.date_range("2024-01-01 00:00", periods=6, freq="1h", tz="UTC")
    df = pd.DataFrame({
        schema.OPEN: [1, 1, 1, 1, 1, 1.0],
        schema.HIGH: [1.1, 1.3, 1.2, 1.0, 1.0, 1.0],
        schema.LOW: [0.9, 0.8, 0.95, 1.0, 1.0, 1.0],
        schema.CLOSE: [1, 1, 1, 1, 1, 1.0],
        "in_tokyo": [True, True, True, False, False, False],
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    out = levels.add_tokyo_session_levels(df)
    # Acumulado dentro de la sesión: tras 3 barras hi=1.3, lo=0.8.
    assert out["tokyo_hi"].iloc[0] == 1.1
    assert out["tokyo_hi"].iloc[1] == 1.3
    assert out["tokyo_lo"].iloc[1] == 0.8
    assert out["tokyo_hi"].iloc[2] == 1.3   # expanding, no baja
    assert np.isnan(out["tokyo_hi"].iloc[3])  # fuera de sesión
