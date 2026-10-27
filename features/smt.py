"""SMT (Smart Money Technique) — divergencia 6A vs 6N (ADR-016).

SMT clásico: dos activos correlacionados (aquí 6A y 6N, ambas divisas
commodity frente al USD, CME) deberían confirmar los mismos extremos. Si uno
hace un nuevo extremo (higher high / lower low) y el otro NO lo confirma, eso
es divergencia — señal de que el movimiento del primero no tiene respaldo real
y es candidato a reversión.

**Limitación de granularidad (documentada, no se oculta):** `data.sources.yahoo_futures`
solo trae 6A y 6N en D1 (ADR-006 ya documentó esto para 6A; 6N hereda la misma
restricción de la fuente). Por eso SMT aquí es una confirmación a nivel D1 (el
mismo nivel que el bias HTF de `features.bias`), NO una confirmación M5 como
MSS/CISD (`features.mss_cisd`) — es una limitación real de datos, no una
aproximación deliberada. Si en el futuro se ingiere 6N intradía (fuente
distinta a Yahoo), este módulo podría extenderse a M5, pero eso es una decisión
de datos nueva, no de este ADR.

Point-in-time: usa exclusivamente `features.structure.add_structure` (ya
confirmado con retraso `k`) y `merge_asof` backward para alinear 6N sobre el
calendario de 6A (mismo patrón que `features.cross_asset`), así que nunca mira
un valor de 6N con timestamp futuro respecto a la barra de 6A evaluada.
"""

from __future__ import annotations

import pandas as pd

from data import schema
from features import structure
from features.cross_asset import _merge_series

__all__ = ["add_smt_divergence"]


def _confirmed_divergence(
    a_values: pd.Series,
    b_values: pd.Series,
    confirmed_mask: pd.Series,
    *,
    higher: bool,
) -> pd.Series:
    """Marca divergencia en las barras `confirmed_mask`: `a` hace un nuevo
    extremo (más alto si `higher=True`, más bajo si `higher=False`) respecto a
    su propio extremo confirmado anterior, pero `b` NO lo hace en el mismo
    intervalo (comparando los mismos dos puntos en el tiempo, no una ventana
    arbitraria).
    """
    out = pd.Series(False, index=a_values.index)
    idx = a_values.index[confirmed_mask]
    if len(idx) < 2:
        return out
    a_sub = a_values.loc[idx]
    b_sub = b_values.loc[idx]
    a_prev = a_sub.shift(1)
    b_prev = b_sub.shift(1)
    if higher:
        a_new_extreme = a_sub > a_prev
        b_new_extreme = b_sub > b_prev
    else:
        a_new_extreme = a_sub < a_prev
        b_new_extreme = b_sub < b_prev
    div = a_new_extreme & ~b_new_extreme & a_prev.notna() & b_prev.notna()
    out.loc[div.index[div]] = True
    return out


def add_smt_divergence(
    a_d1: pd.DataFrame,
    b_d1: pd.DataFrame,
    *,
    k: int = 2,
) -> pd.DataFrame:
    """Añade `smt_bear`/`smt_bull` (bool, D1) al dataset de `a_d1` (6A).

    Args:
        a_d1: D1 del activo primario (6A). Se le aplica `add_structure` si no
            trae ya las columnas de estructura.
        b_d1: D1 del activo de comparación (6N). Igual.

    Returns:
        Copia de `a_d1` con `smt_bear` (6A hace higher-high, 6N no confirma) y
        `smt_bull` (6A hace lower-low, 6N no confirma).
    """
    a = a_d1 if "swing_high_confirmed" in a_d1.columns else structure.add_structure(a_d1, k=k)
    b = b_d1 if "swing_high_confirmed" in b_d1.columns else structure.add_structure(b_d1, k=k)

    out = a.copy()
    out = _merge_series(out, b["last_swing_high"], "_b_last_swing_high")
    out = _merge_series(out, b["last_swing_low"], "_b_last_swing_low")

    out["smt_bear"] = _confirmed_divergence(
        out["last_swing_high"], out["_b_last_swing_high"], out["swing_high_confirmed"], higher=True,
    )
    out["smt_bull"] = _confirmed_divergence(
        out["last_swing_low"], out["_b_last_swing_low"], out["swing_low_confirmed"], higher=False,
    )
    return out.drop(columns=["_b_last_swing_high", "_b_last_swing_low"])
