"""Tests de estructura de mercado sobre datos sintéticos con respuesta conocida (ADR-004)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features import structure


def _frame(open_, high, low, close) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(close), freq="1h", tz="UTC")
    df = pd.DataFrame(
        {schema.OPEN: open_, schema.HIGH: high, schema.LOW: low, schema.CLOSE: close},
        index=idx,
    )
    df.index.name = schema.TIMESTAMP
    return df


def test_swing_high_detected_and_confirmed_with_lag():
    # Pico claro en la barra 4 (índice 4). Con k=2 se confirma en la barra 6.
    high = [1, 2, 3, 4, 9, 4, 3, 2, 1, 1]
    low = [h - 0.5 for h in high]
    close = high
    df = _frame(close, high, low, close)
    out = structure.add_structure(df, k=2, sweep_lookback=50)

    # La confirmación aparece con retraso k=2 (en la barra 6), no en la 4.
    assert not out["swing_high_confirmed"].iloc[4]
    assert out["swing_high_confirmed"].iloc[6]
    # El precio del último swing high confirmado (a partir de la barra 6) es 9.
    assert out["last_swing_high"].iloc[6] == 9


def test_liquidity_sweep_high():
    # Swing high = 10 en barra 2 (confirmado en barra 4). Luego una barra penetra
    # 10 en el high pero cierra por debajo => liquidity sweep.
    high =  [8, 9, 10, 9, 8,  8,  11, 8]
    low =   [7, 8, 9,  8, 7,  7,  8,  7]
    close = [8, 9, 9,  8, 7,  7,  9,  7]   # barra 6: high 11 > 10, close 9 < 10
    open_ = close
    df = _frame(open_, high, low, close)
    out = structure.add_structure(df, k=2, sweep_lookback=50)

    assert out["last_swing_high"].iloc[6] == 10
    assert out["liquidity_sweep_high"].iloc[6]
    # Una barra que no penetra el nivel no marca sweep.
    assert not out["liquidity_sweep_high"].iloc[5]


def test_sweep_respects_lookback_window():
    # Swing high lejano; si el sweep ocurre más allá de sweep_lookback, no cuenta.
    n = 60
    high = [10.0] + [5.0] * (n - 1)
    high[2] = 12.0  # swing high fuerte en barra 2 (confirmado barra 4)
    low = [h - 1 for h in high]
    close = [5.0] * n
    high[55] = 13.0  # penetra 12 pero barra 55 está > 50 barras tras la 2
    close[55] = 5.0
    df = _frame(close, high, low, close)
    out = structure.add_structure(df, k=2, sweep_lookback=50)
    # Fuera de la ventana de lookback => no es sweep válido del swing de la barra 2.
    assert not out["liquidity_sweep_high"].iloc[55]
