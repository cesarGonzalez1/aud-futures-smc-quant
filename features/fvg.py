"""Fair Value Gaps (FVG) e Inverse FVG en M5 (ADR-007 anexo, extiende ADR-004).

FVG de 3 velas (índices t-2, t-1, t; se marca en la vela t = tercera):
  - alcista: low[t] > high[t-2]  → zona [high[t-2], low[t]]
  - bajista: high[t] < low[t-2]  → zona [high[t], low[t-2]]
Filtro de tamaño mínimo: amplitud del gap ≥ `min_atr_frac` × ATR (default 0.1).

Inverse FVG: una vela posterior cierra MÁS ALLÁ del límite opuesto de una FVG
activa, invalidándola; esa vela de cierre es la señal de confirmación:
  - FVG alcista (límite inferior = high[t-2]) → IFVG bajista si un cierre posterior
    cae por debajo de ese límite inferior.
  - FVG bajista (límite superior = low[t-2]) → IFVG alcista si un cierre posterior
    sube por encima de ese límite superior.

Todo es point-in-time: cada columna en la barra t usa solo datos ≤ t (la FVG se
marca en su tercera vela; el IFVG compara el cierre actual contra FVGs ya formadas).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema


def detect_fvg(df: pd.DataFrame, *, atr_col: str = "atr", min_atr_frac: float = 0.1) -> pd.DataFrame:
    """Marca FVGs en la tercera vela. Requiere columna ATR (`atr_col`).

    Añade: fvg_bull, fvg_bear (bool), fvg_low, fvg_high (float, límites de la zona).
    """
    out = df.copy()
    high = out[schema.HIGH].to_numpy()
    low = out[schema.LOW].to_numpy()
    atr = out[atr_col].to_numpy() if atr_col in out.columns else np.full(len(out), np.nan)
    n = len(out)

    bull = np.zeros(n, dtype=bool)
    bear = np.zeros(n, dtype=bool)
    z_low = np.full(n, np.nan)
    z_high = np.full(n, np.nan)

    for t in range(2, n):
        thr = (min_atr_frac * atr[t]) if not np.isnan(atr[t]) else 0.0
        # Alcista: gap entre high[t-2] y low[t].
        if low[t] > high[t - 2] and (low[t] - high[t - 2]) >= thr:
            bull[t] = True
            z_low[t], z_high[t] = high[t - 2], low[t]
        # Bajista: gap entre high[t] y low[t-2].
        elif high[t] < low[t - 2] and (low[t - 2] - high[t]) >= thr:
            bear[t] = True
            z_low[t], z_high[t] = high[t], low[t - 2]

    out["fvg_bull"] = bull
    out["fvg_bear"] = bear
    out["fvg_low"] = z_low
    out["fvg_high"] = z_high
    return out


def detect_ifvg(df: pd.DataFrame, *, max_active: int = 200) -> pd.DataFrame:
    """Marca confirmaciones Inverse FVG. Requiere columnas de `detect_fvg`.

    Añade: ifvg_bull, ifvg_bear (bool). Una vela que invalida una FVG activa (cierra
    más allá de su límite opuesto) marca el IFVG en la dirección contraria a la FVG.

    Args:
        max_active: tope de FVGs activas rastreadas (evita crecimiento ilimitado).
    """
    out = df.copy()
    close = out[schema.CLOSE].to_numpy()
    fbull = out["fvg_bull"].to_numpy()
    fbear = out["fvg_bear"].to_numpy()
    flow = out["fvg_low"].to_numpy()
    fhigh = out["fvg_high"].to_numpy()
    n = len(out)

    ifvg_bull = np.zeros(n, dtype=bool)
    ifvg_bear = np.zeros(n, dtype=bool)
    active: list[tuple[str, float, float]] = []  # (dir, low, high)

    for t in range(n):
        c = close[t]
        still: list[tuple[str, float, float]] = []
        for direction, lo, hi in active:
            if direction == "bull" and c < lo:      # FVG alcista invalidada -> IFVG bajista
                ifvg_bear[t] = True
            elif direction == "bear" and c > hi:     # FVG bajista invalidada -> IFVG alcista
                ifvg_bull[t] = True
            else:
                still.append((direction, lo, hi))
        active = still[-max_active:]
        # Registrar la FVG creada en esta barra (se vuelve candidata a invalidarse luego).
        if fbull[t]:
            active.append(("bull", flow[t], fhigh[t]))
        elif fbear[t]:
            active.append(("bear", flow[t], fhigh[t]))

    out["ifvg_bull"] = ifvg_bull
    out["ifvg_bear"] = ifvg_bear
    return out


def add_fvg_features(df: pd.DataFrame, *, atr_col: str = "atr", min_atr_frac: float = 0.1) -> pd.DataFrame:
    """Conveniencia: detecta FVG y luego IFVG en una pasada."""
    return detect_ifvg(detect_fvg(df, atr_col=atr_col, min_atr_frac=min_atr_frac))
