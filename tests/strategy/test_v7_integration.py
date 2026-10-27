"""Test de integración de V7 (ADR-015): confirmación CISD + target Quarter Theory."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from strategy.liquidity_sweep_ifvg_v7 import generate_trades_v7


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


def test_v7_confirms_via_cisd_and_targets_quarter_level():
    m5 = _base_m5()
    idx = m5.index

    # Capa 1: sweep bajista en la barra 0 (equal high barrido).
    m5.loc[idx[0], "equal_high_recent"] = True
    m5.loc[idx[0], "liquidity_sweep_high"] = True
    m5.loc[idx[0], schema.OPEN] = 1.00  # referencia para CISD

    # Capa 2: CISD confirma en la barra 5 (cierre < 1.00, MSS queda en False).
    m5.loc[idx[5], schema.CLOSE] = 0.99

    # Capa 4: IFVG confirma en la barra 10 (después de la confirmación) -> entrada en barra 11.
    m5.loc[idx[10], "ifvg_bear"] = True
    m5.loc[idx[11], schema.OPEN] = 0.6543  # precio de entrada realista para Quarter Theory

    confluence = pd.DataFrame(
        {"direction": [-1], "confidence": ["alta"]},
        index=pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")]),
    )

    trades, confidences, sources, confirmations, quarter_aligned = generate_trades_v7(
        m5, _empty_h1(), confluence,
    )

    assert len(trades) == 1
    t = trades[0]
    assert t.side == "short"
    assert t.entry_price == 0.6543
    assert confirmations[0] == "cisd"
    assert sources[0] == "quarter_level"
    assert t.target == 0.6525          # cuarto inmediato hacia abajo (features.quarter_theory)
    assert t.stop == 1.10              # heredado de V5/V4 (swing H1)


def test_v7_no_trade_without_mss_or_cisd_confirmation():
    m5 = _base_m5()
    idx = m5.index
    m5.loc[idx[0], "equal_high_recent"] = True
    m5.loc[idx[0], "liquidity_sweep_high"] = True
    # Ningún cierre rompe el open de referencia (1.00) ni al alza ni a la baja de forma bajista real,
    # y mss_bear queda en False en toda la ventana -> ninguna confirmación.
    m5.loc[idx[10], "ifvg_bear"] = True  # aunque haya IFVG, sin confirmación previa no debe operar

    confluence = pd.DataFrame(
        {"direction": [-1], "confidence": ["alta"]},
        index=pd.DatetimeIndex([pd.Timestamp("2024-01-02", tz="UTC")]),
    )

    trades, *_ = generate_trades_v7(m5, _empty_h1(), confluence)
    assert len(trades) == 0
