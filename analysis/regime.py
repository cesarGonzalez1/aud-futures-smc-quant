"""Detección de régimen por reglas (ADR-003 + enmienda Fase 3).

Baseline obligatorio SIN ML (Filosofía ML: modelos simples primero). Tres capas:
  - `regime_trend`: `trending` / `range`, con histéresis sobre ADX (entra >27,
    sale <23) y consistencia de signo de la pendiente de EMA(50).
  - `regime_vol`: `alta` / `normal` / `baja` según el percentil móvil de ATR(14)
    en una ventana de 90 días (trailing, point-in-time).
  - `regime`: producto cartesiano `"{trend}|{vol}"`.

Point-in-time: la ventana del percentil es trailing (solo pasado); puede cruzar
el borde de una cohorte (es PIT-safe), solo la agregación/reporte es por cohorte.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

TREND_COL = "regime_trend"
VOL_COL = "regime_vol"
ATR_PCT_COL = "atr_pct"
REGIME_COL = "regime"


def add_trend_regime(
    df: pd.DataFrame,
    *,
    adx_enter: float = 27.0,
    adx_exit: float = 23.0,
    slope_window: int = 3,
) -> pd.DataFrame:
    """Añade `regime_trend` con histéresis ADX + consistencia de pendiente EMA(50).

    La banda 27/23 rodea el umbral 25 de ADR-003 para evitar whipsaw (enmienda).
    """
    out = df.copy()
    adx = out["adx"].to_numpy()
    slope = out["ema_trend"].diff()
    up = slope.rolling(slope_window).apply(lambda x: bool(np.all(x > 0)), raw=True)
    down = slope.rolling(slope_window).apply(lambda x: bool(np.all(x < 0)), raw=True)
    consistent = ((up == 1) | (down == 1)).to_numpy()

    regime = np.empty(len(out), dtype=object)
    state = "range"
    for i in range(len(out)):
        a = adx[i]
        if not np.isnan(a):
            if state == "range":
                if a > adx_enter and consistent[i]:
                    state = "trending"
            else:  # trending
                if a < adx_exit or not consistent[i]:
                    state = "range"
        regime[i] = state
    out[TREND_COL] = regime
    return out


def add_vol_regime(
    df: pd.DataFrame,
    *,
    window_days: int = 90,
    bars_per_day: int = 24,
    low_pct: float = 30.0,
    high_pct: float = 70.0,
) -> pd.DataFrame:
    """Añade `regime_vol` según el percentil móvil (trailing) de ATR(14).

    Args:
        window_days: tamaño de la ventana en días (default 90, ADR-003).
        bars_per_day: barras por día del timeframe (H1 => 24).
        low_pct/high_pct: cortes de percentil para baja/alta.
    """
    out = df.copy()
    window = window_days * bars_per_day
    pct = out["atr"].rolling(window, min_periods=window // 2).rank(pct=True) * 100.0
    out[ATR_PCT_COL] = pct

    vol = pd.Series(index=out.index, dtype=object)
    vol[pct > high_pct] = "alta"
    vol[pct < low_pct] = "baja"
    vol[(pct >= low_pct) & (pct <= high_pct)] = "normal"
    out[VOL_COL] = vol.where(pct.notna(), other=np.nan)
    return out


def add_regime(df: pd.DataFrame, *, trend_kwargs: dict | None = None,
               vol_kwargs: dict | None = None) -> pd.DataFrame:
    """Añade las tres columnas de régimen (trend, vol y combinado)."""
    out = add_trend_regime(df, **(trend_kwargs or {}))
    out = add_vol_regime(out, **(vol_kwargs or {}))
    combined = out[TREND_COL].astype(str) + "|" + out[VOL_COL].astype(str)
    out[REGIME_COL] = combined.where(out[VOL_COL].notna(), other=np.nan)
    return out
