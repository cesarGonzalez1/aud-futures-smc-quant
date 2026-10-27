"""Confirmaciones de reversión: MSS y CISD (capa 2 de la jerarquía, ADR-015).

Extiende `features/structure.py` (ADR-004), no reimplementa nada de swings o
sweeps — solo añade dos formas de CONFIRMAR que el sweep de liquidez se está
convirtiendo en reversión real, antes de buscar la zona de entrada (IFVG):

  - **MSS (Market Structure Shift):** un cierre rompe el último swing
    CONFIRMADO del lado opuesto (`last_swing_high`/`last_swing_low`,
    point-in-time por construcción en `features/structure.py`). Rompe swing
    high confirmado => shift alcista; rompe swing low confirmado => shift
    bajista.
  - **CISD (Change in State of Delivery):** el primer cierre, dentro de una
    ventana posterior a un precio de referencia (el open de la vela que hizo
    el sweep), que cierra más allá de ese open en la dirección de la reversión.
    Es una función de búsqueda (no una columna precalculada) porque depende de
    un evento puntual (la vela del sweep), igual que
    `features.liquidity_target.next_unfilled_fvg_target` es una búsqueda y no
    una columna.

Point-in-time: `add_mss_flags` solo usa columnas ya confirmadas con retraso
(`last_swing_high`/`last_swing_low`); `find_cisd` solo mira barras con
timestamp >= inicio de la ventana provista por quien llama (nunca hacia atrás
del evento que la originó).
"""

from __future__ import annotations

import pandas as pd

from data import schema

__all__ = ["add_mss_flags", "find_cisd"]


def add_mss_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Añade `mss_bull`/`mss_bear` (bool).

    Requiere `last_swing_high`/`last_swing_low` (`features.structure.add_structure`,
    ya point-in-time). No usa el flag crudo de swing centrado, solo el confirmado.
    """
    out = df.copy()
    if "last_swing_high" not in out.columns or "last_swing_low" not in out.columns:
        raise ValueError("Faltan last_swing_high/last_swing_low (aplica features.structure.add_structure primero)")
    close = out[schema.CLOSE]
    out["mss_bull"] = close > out["last_swing_high"]
    out["mss_bear"] = close < out["last_swing_low"]
    return out


def find_cisd(
    window: pd.DataFrame,
    reference_open: float,
    direction: str,
) -> pd.Timestamp | None:
    """Busca el primer cierre en `window` que rompe `reference_open` en la
    dirección de la reversión.

    Args:
        window: barras a partir del evento de origen (p.ej. la vela del sweep),
            EXCLUSIVE del propio evento — quien llama define la ventana.
        reference_open: open de la vela que originó la reversión (p.ej. la vela
            H1 del sweep).
        direction: "bull" (cierre por ENCIMA de `reference_open`) o "bear"
            (cierre por DEBAJO).

    Returns:
        Timestamp de la primera barra que confirma CISD, o None si ninguna lo hace.
    """
    if direction not in ("bull", "bear"):
        raise ValueError(f"direction debe ser 'bull' o 'bear', recibido {direction!r}")
    closes = window[schema.CLOSE]
    hit = closes[closes > reference_open] if direction == "bull" else closes[closes < reference_open]
    return hit.index[0] if len(hit) else None
