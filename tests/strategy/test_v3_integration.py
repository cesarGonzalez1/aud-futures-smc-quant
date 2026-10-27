"""Integración V3 (ADR-009): la misma mecánica AMD, ahora enteramente en M5.

La lógica de swing/sweep/OB/FVG no cambia (ya testeada sobre datos sintéticos en
sus módulos); aquí se verifica que la estrategia V3 opera con sweep + confirmación
en el mismo timeframe M5 y respeta la precondición de acumulación.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from strategy import liquidity_sweep_ifvg_v3 as v3


def _m5_bearish(in_acc: bool):
    """M5: sweep de PDH en la barra 0, IFVG bajista en barra 2, precio baja al target."""
    idx = pd.date_range("2024-01-02 00:00", periods=9, freq="5min", tz="UTC")
    n = len(idx)
    df = pd.DataFrame({
        schema.OPEN:  [1.199, 1.18, 1.175, 1.17, 1.16, 1.14, 1.12, 1.10, 1.09],
        schema.HIGH:  [1.205, 1.182, 1.176, 1.171, 1.161, 1.141, 1.121, 1.101, 1.091],
        schema.LOW:   [1.195, 1.176, 1.169, 1.15, 1.13, 1.11, 1.095, 1.09, 1.085],
        schema.CLOSE: [1.198, 1.178, 1.175, 1.16, 1.14, 1.12, 1.10, 1.095, 1.088],
        # niveles/POI:
        "pdh": 1.20, "pdl": 1.05, "pwh": np.nan, "pwl": np.nan,
        "tokyo_hi": np.nan, "tokyo_lo": np.nan, "acc_high": np.nan, "acc_low": np.nan,
        "equal_high": False, "equal_low": False,
        "ob_bull_high": np.nan, "ob_bear_low": np.nan,
        "last_swing_high": 1.21, "last_swing_low": 1.10,
        "in_accumulation": in_acc,
        # IFVG bajista en barra 2:
        "ifvg_bull": [False] * n,
        "ifvg_bear": [False, False, True, False, False, False, False, False, False],
    }, index=pd.DatetimeIndex(idx, name=schema.TIMESTAMP))
    return df


def test_v3_all_mechanics_on_m5():
    bias = pd.Series({pd.Timestamp("2024-01-02", tz="UTC"): -1})
    # barra 0 (00:00): high 1.205 > pdh 1.20 y close 1.198 < 1.20 => sweep de máximos.
    # IFVG bajista en barra 2 (00:10); entrada en apertura de barra 3 (00:15).
    trades = v3.generate_trades_v3(_m5_bearish(True), bias, window_start=0, window_end=4,
                                   confirm_lookback=12)
    assert len(trades) == 1
    t = trades[0]
    assert t.side == "short"
    assert np.isclose(t.entry_price, 1.17)   # open de la barra 3
    assert np.isclose(t.stop, 1.205)          # high de la barra de sweep (M5)
    assert np.isclose(t.target, 1.10)         # swing bajo M5
    assert t.outcome == "target"


def test_v3_requires_accumulation():
    bias = pd.Series({pd.Timestamp("2024-01-02", tz="UTC"): -1})
    assert v3.generate_trades_v3(_m5_bearish(False), bias) == []
