"""Quarter Theory — niveles .00/.25/.50/.75 (ADR-015).

Divide cada "big figure" (0.0100 en AUD/USD y 6A, misma escala de cotización,
ADR-006) en 4 cuartos iguales de 0.0025: ..., X.7000, X.7025, X.7050, X.7075,
X.7100, ... Es CONTEXTO (capa 3 de la jerarquía discrecional, ADR-015), no un
gate obligatorio: se expone como columna informativa (`near_quarter_level`) y
como fuente adicional de target en `features.liquidity_target`, exactamente
igual que `day_range`/`fvg_h1` ya son informativas/opcionales en V5 (ADR-011) —
no se excluyen operaciones por esto, para no repetir el error de sobre-filtrar
y perder tamaño de muestra (sección 6.2 / lección de V2-V5).

Point-in-time: los niveles se derivan solo del precio en la barra `t` (no usan
información futura); no hay ventana temporal que pueda mirar hacia adelante.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema

DEFAULT_STEP = 0.0025  # 1/4 de "big figure" (0.0100) — AUD/USD y 6A (ADR-006)


def nearest_quarter_levels(price: float, *, step: float = DEFAULT_STEP) -> tuple[float, float]:
    """Devuelve (cuarto_inferior, cuarto_superior) que enmarcan `price`.

    Ambos son múltiplos exactos de `step`. Si `price` cae exactamente sobre un
    cuarto, ese mismo valor es tanto el inferior como el superior.
    """
    lower = np.floor(price / step) * step
    upper = np.ceil(price / step) * step
    if upper == lower:
        upper = lower + step
    return round(float(lower), 10), round(float(upper), 10)


def add_quarter_context(
    df: pd.DataFrame,
    *,
    price_col: str = schema.CLOSE,
    step: float = DEFAULT_STEP,
    atr_col: str = "atr",
    proximity_atr_frac: float = 0.15,
) -> pd.DataFrame:
    """Añade columnas de contexto Quarter Theory (point-in-time, por barra).

    Añade:
        quarter_lower / quarter_upper: cuartos que enmarcan el precio de la barra.
        dist_to_nearest_quarter: distancia absoluta al cuarto más cercano.
        near_quarter_level: bool, True si `dist_to_nearest_quarter` está dentro
            de `proximity_atr_frac` * ATR de la barra (o de `step`/2 si no hay
            columna ATR disponible). Informativo — no es un filtro obligatorio.
    """
    out = df.copy()
    price = out[price_col].to_numpy(dtype=float)
    lower = np.floor(price / step) * step
    upper = lower + step
    dist_lower = price - lower
    dist_upper = upper - price
    dist = np.minimum(dist_lower, dist_upper)

    out["quarter_lower"] = np.round(lower, 10)
    out["quarter_upper"] = np.round(upper, 10)
    out["dist_to_nearest_quarter"] = dist

    if atr_col in out.columns:
        threshold = out[atr_col].to_numpy(dtype=float) * proximity_atr_frac
        threshold = np.where(np.isnan(threshold), step / 2.0, threshold)
    else:
        threshold = np.full(len(out), step / 2.0)
    out["near_quarter_level"] = dist <= threshold
    return out


def quarter_target(
    entry_price: float,
    side: str,
    *,
    step: float = DEFAULT_STEP,
    n_levels: int = 1,
) -> float:
    """Cuarto objetivo en la dirección del trade, `n_levels` cuartos por delante
    del cuarto inmediatamente siguiente a `entry_price` (target de la jerarquía
    de salida, ADR-015: "Targets: BOS, Quarter levels").

    Para `side='long'`: primer múltiplo de `step` estrictamente mayor a
    `entry_price`, avanzado `n_levels - 1` cuartos adicionales.
    Para `side='short'`: simétrico hacia abajo.
    """
    if side == "long":
        first = np.floor(entry_price / step) * step + step
        return round(float(first + (n_levels - 1) * step), 10)
    first = np.ceil(entry_price / step) * step - step
    return round(float(first - (n_levels - 1) * step), 10)
