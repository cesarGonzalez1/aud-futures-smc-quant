"""Integración end-to-end de la hipótesis ADR-007 sobre frames sintéticos.

Se construye un escenario BAJISTA conocido: bias bajista, un sweep de máximos en H1
sobre el PDH, un IFVG bajista en M5 dentro de la ventana, y un swing bajo H1 como
target. Se verifica que `generate_trades` produce exactamente una operación short
con los precios esperados.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from strategy import liquidity_sweep_ifvg as strat


def test_bias_from_d1_shifts_one_day():
    # 8 días con ADX alto y EMA decreciente monótona: la histéresis entra a
    # 'trending' tras varias barras de pendiente consistente => bias bajista, y el
    # bias del día se toma del día anterior (shift). Se verifica ambas cosas.
    idx = pd.date_range("2024-01-01", periods=8, freq="1D", tz="UTC")
    d1 = pd.DataFrame(index=idx)
    d1.index.name = schema.TIMESTAMP
    d1["adx"] = [30.0] * 8
    d1["ema_trend"] = [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3]  # pendiente < 0 consistente
    bias = strat.daily_bias_from_d1(d1)
    assert bias.iloc[0] == 0     # primer día no tiene día previo
    assert bias.iloc[-1] == -1   # ya establecido en trending bajista


def _h1_bearish_sweep():
    # Ventana 00-04 UTC del 2024-01-02. PDH=1.20. La barra 02:00 penetra 1.20 y
    # cierra debajo => sweep de máximos. Swing bajo previo = 1.10 (target).
    idx = pd.date_range("2024-01-02 00:00", periods=5, freq="1h", tz="UTC")
    df = pd.DataFrame({
        schema.OPEN:  [1.19, 1.19, 1.199, 1.18, 1.17],
        schema.HIGH:  [1.195, 1.198, 1.205, 1.19, 1.18],  # barra idx2 high=1.205 > PDH
        schema.LOW:   [1.185, 1.188, 1.195, 1.16, 1.15],
        schema.CLOSE: [1.19, 1.195, 1.198, 1.17, 1.16],   # barra idx2 close=1.198 < 1.20
        "pdh": 1.20, "pdl": 1.05,
        "tokyo_hi": np.nan, "tokyo_lo": np.nan,
        "last_swing_high": 1.21, "last_swing_low": 1.10,
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    return df


def _m5_bearish_ifvg():
    # M5 tras el cierre de la barra H1 de sweep (03:00-04:00). Un IFVG bajista en
    # 03:10; entrada en la apertura de 03:15. Precio baja hasta tocar 1.10 (target).
    idx = pd.date_range("2024-01-02 03:00", periods=8, freq="5min", tz="UTC")
    n = len(idx)
    df = pd.DataFrame({
        schema.OPEN:  [1.18, 1.178, 1.175, 1.17, 1.16, 1.14, 1.12, 1.10],
        schema.HIGH:  [1.182, 1.18, 1.176, 1.171, 1.161, 1.141, 1.121, 1.101],
        schema.LOW:   [1.176, 1.174, 1.169, 1.15, 1.13, 1.11, 1.095, 1.095],
        schema.CLOSE: [1.178, 1.175, 1.17, 1.16, 1.14, 1.12, 1.10, 1.098],
        "ifvg_bull": [False] * n,
        "ifvg_bear": [False, False, True, False, False, False, False, False],
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    return df


def test_generate_one_short_trade():
    h1 = _h1_bearish_sweep()
    m5 = _m5_bearish_ifvg()
    bias = pd.Series({pd.Timestamp("2024-01-02", tz="UTC"): -1})

    trades = strat.generate_trades(h1, m5, bias, window_start=0, window_end=4,
                                   confirm_lookback_m5=12)
    assert len(trades) == 1
    t = trades[0]
    assert t.side == "short"
    # Entrada = apertura de la barra M5 siguiente a la confirmación (03:15 = idx3).
    assert np.isclose(t.entry_price, 1.17)
    # Stop = high de la barra H1 del sweep (1.205).
    assert np.isclose(t.stop, 1.205)
    # Target = swing bajo H1 (1.10). El precio llega a 1.095 => target alcanzado.
    assert np.isclose(t.target, 1.10)
    assert t.outcome == "target"
    assert t.r_multiple > 0


def test_no_trade_when_bias_zero():
    h1 = _h1_bearish_sweep()
    m5 = _m5_bearish_ifvg()
    bias = pd.Series({pd.Timestamp("2024-01-02", tz="UTC"): 0})  # sin bias => no opera
    assert strat.generate_trades(h1, m5, bias) == []
