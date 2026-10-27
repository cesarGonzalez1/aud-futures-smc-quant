"""Tests de detección de régimen (ADR-003 + enmienda: histéresis, percentil)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis import regime as R


def _frame(n: int) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    df = pd.DataFrame(index=idx)
    df.index.name = "timestamp"
    return df


def test_trend_hysteresis():
    # ADX cruza hacia arriba (>27) y luego cae (<23); EMA siempre creciente.
    adx = [10, 10, 10, 28, 28, 28, 28, 22, 22, 22]
    df = _frame(len(adx))
    df["adx"] = adx
    df["ema_trend"] = np.arange(len(adx), dtype=float)  # pendiente > 0 consistente
    out = R.add_trend_regime(df, adx_enter=27, adx_exit=23, slope_window=3)
    reg = out[R.TREND_COL].tolist()
    assert reg[2] == "range"       # antes de superar el umbral
    assert reg[3] == "trending"    # entra con ADX 28 > 27 y pendiente consistente
    assert reg[6] == "trending"    # se mantiene (ADX no baja de 23)
    assert reg[7] == "range"       # sale con ADX 22 < 23


def test_trend_needs_slope_consistency():
    # ADX alto pero EMA plana => sin consistencia de pendiente => no entra trending.
    adx = [30] * 8
    df = _frame(8)
    df["adx"] = adx
    df["ema_trend"] = np.ones(8, dtype=float)  # pendiente 0 => no consistente
    out = R.add_trend_regime(df)
    assert (out[R.TREND_COL] == "range").all()


def test_vol_regime_high_and_low():
    df = _frame(10)
    df["atr"] = np.arange(1, 11, dtype=float)  # creciente: último = máximo del trailing
    out = R.add_vol_regime(df, window_days=1, bars_per_day=4, low_pct=30, high_pct=70)
    assert out[R.VOL_COL].iloc[-1] == "alta"

    df2 = _frame(10)
    df2["atr"] = np.arange(10, 0, -1, dtype=float)  # decreciente: último = mínimo
    out2 = R.add_vol_regime(df2, window_days=1, bars_per_day=4, low_pct=30, high_pct=70)
    assert out2[R.VOL_COL].iloc[-1] == "baja"


def test_combined_regime_label():
    adx = [30] * 6
    df = _frame(6)
    df["adx"] = adx
    df["ema_trend"] = np.arange(6, dtype=float)
    df["atr"] = np.arange(1, 7, dtype=float)
    out = R.add_regime(df, vol_kwargs={"window_days": 1, "bars_per_day": 2})
    last = out[R.REGIME_COL].iloc[-1]
    assert "|" in last  # formato "{trend}|{vol}"
