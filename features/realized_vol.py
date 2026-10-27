"""Volatilidad realizada — feature point-in-time y TARGET forward (secciones 2, 7.2).

Estimador de Garman-Klass por barra (usa OHLC, más eficiente que solo cierres):
    gk = 0.5 * ln(H/L)^2 - (2 ln2 - 1) * ln(C/O)^2

Dos usos distintos, claramente separados:
  - `add_realized_vol`: volatilidad realizada HACIA ATRÁS (rolling). Es un FEATURE
    point-in-time (solo pasado) — puede usarse como entrada de un modelo.
  - `add_forward_vol_target`: volatilidad realizada de las próximas N barras. Es el
    TARGET de la sección 2 (label). Usa datos FUTUROS por definición — NUNCA debe
    usarse como feature de entrada, solo como variable dependiente en Fase 3. Por
    eso su columna lleva prefijo `target_` y se EXCLUYE del test anti-look-ahead.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema

_GK_C = 2.0 * np.log(2.0) - 1.0


def _garman_klass_per_bar(df: pd.DataFrame) -> pd.Series:
    """Varianza de Garman-Klass por barra (no anualizada)."""
    o = df[schema.OPEN]
    h = df[schema.HIGH]
    low = df[schema.LOW]
    c = df[schema.CLOSE]
    hl = np.log(h / low)
    co = np.log(c / o)
    return 0.5 * hl**2 - _GK_C * co**2


def add_realized_vol(df: pd.DataFrame, *, window: int = 24) -> pd.DataFrame:
    """Volatilidad realizada rolling hacia atrás (feature point-in-time).

    Args:
        window: nº de barras de la ventana (default 24 = ~1 día en H1).

    Returns:
        Copia con columna `realized_vol` = sqrt(suma de GK en la ventana previa).
    """
    out = df.copy()
    gk = _garman_klass_per_bar(out).clip(lower=0)
    out["realized_vol"] = np.sqrt(gk.rolling(window).sum())
    return out


def add_forward_vol_target(df: pd.DataFrame, *, horizon: int = 6) -> pd.DataFrame:
    """TARGET: volatilidad realizada de las próximas `horizon` barras (sección 2).

    ADVERTENCIA: usa barras FUTURAS. Es el label de Fase 3, no un feature. Las
    últimas `horizon` barras quedan NaN (no hay futuro suficiente).

    Args:
        horizon: N barras hacia adelante (default 6 ≈ una sesión de solapamiento).

    Returns:
        Copia con columna `target_fwd_vol_{horizon}`.
    """
    out = df.copy()
    gk = _garman_klass_per_bar(out).clip(lower=0)
    # rolling(horizon).sum() en el índice u = suma de gk[u-horizon+1 .. u].
    # Desplazando -horizon, en el índice t queda la suma de gk[t+1 .. t+horizon].
    fwd = gk.rolling(horizon).sum().shift(-horizon)
    out[f"target_fwd_vol_{horizon}"] = np.sqrt(fwd)
    return out
