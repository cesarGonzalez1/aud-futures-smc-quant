"""Salida jerárquica "próximo punto de liquidez" (ADR-011).

Reemplaza, para la hipótesis V5, el target fijo "swing opuesto" (V1-V4) por una
jerarquía de tres candidatos, evaluada EN ORDEN, deteniéndose en el primero que
aplique (regla fijada de antemano — no se elige a ojo cuál usar en cada caso):

    1. FVG en H1 sin rellenar, en la dirección del movimiento (ventana de lookback
       configurable). Target = borde LEJANO de la zona (relleno completo).
    2. Si el día viene oscilando (regime_vol='baja' en la barra de entrada):
       extremo del día calendario UTC hasta la barra de entrada (day_hi/day_lo,
       point-in-time — nunca el rango completo del día, solo lo visto hasta ahí).
    3. Fallback: swing opuesto más cercano en M5 (misma definición que V1-V4).

Point-in-time: cada regla usa solo datos con timestamp <= entry_time. "Día" =
día calendario UTC desde las 00:00 hasta la barra de entrada (no desde la
apertura de Tokio) — así el extremo del día incluye lo ocurrido en sesiones
previas del mismo día calendario.
"""

from __future__ import annotations

import pandas as pd

from data import schema


def next_unfilled_fvg_target(
    h1_fvg: pd.DataFrame,
    entry_time: pd.Timestamp,
    entry_price: float,
    side: str,
    *,
    lookback_bars: int = 30,
) -> float | None:
    """Busca, en H1, la FVG más cercana (entre las últimas `lookback_bars` velas
    H1 antes de `entry_time`) que esté del lado correcto de `entry_price` (arriba
    si `side='long'`, abajo si `side='short'`) y que NO haya sido rellenada (ningún
    cierre H1 entre su formación y `entry_time` entró en su zona).

    Requiere que `h1_fvg` tenga las columnas de `features.fvg.detect_fvg`
    (fvg_bull, fvg_bear, fvg_low, fvg_high) calculadas sobre H1.

    Returns:
        El borde lejano de la zona más cercana sin rellenar (relleno completo), o
        None si no hay ninguna candidata.
    """
    hist = h1_fvg[h1_fvg.index < entry_time].tail(lookback_bars)
    candidates: list[tuple[pd.Timestamp, float]] = []

    for t, row in hist.iterrows():
        for flag_col in ("fvg_bull", "fvg_bear"):
            if not bool(row.get(flag_col, False)):
                continue
            lo, hi = row.get("fvg_low"), row.get("fvg_high")
            if pd.isna(lo) or pd.isna(hi):
                continue
            if side == "long" and lo > entry_price:
                between = h1_fvg[(h1_fvg.index > t) & (h1_fvg.index < entry_time)]
                filled = ((between[schema.CLOSE] >= lo) & (between[schema.CLOSE] <= hi)).any()
                if not filled:
                    candidates.append((t, float(hi)))  # borde lejano (arriba) para long
            elif side == "short" and hi < entry_price:
                between = h1_fvg[(h1_fvg.index > t) & (h1_fvg.index < entry_time)]
                filled = ((between[schema.CLOSE] >= lo) & (between[schema.CLOSE] <= hi)).any()
                if not filled:
                    candidates.append((t, float(lo)))  # borde lejano (abajo) para short

    if not candidates:
        return None
    # La más cercana en precio (la primera que el movimiento alcanzaría).
    if side == "long":
        return min(v for _, v in candidates)
    return max(v for _, v in candidates)


def resolve_target(
    *,
    h1_fvg: pd.DataFrame,
    m5_row,
    entry_time: pd.Timestamp,
    entry_price: float,
    side: str,
    lookback_bars: int = 30,
) -> tuple[float | None, str]:
    """Aplica la jerarquía de 3 prioridades (ADR-011) y devuelve (target, fuente).

    `fuente` es una de {"fvg_h1", "day_range", "swing_opposite", "none"} — se deja
    explícita en cada operación para poder analizar después qué regla se usó, sin
    que eso influya en el cálculo (es post-hoc, informativo).
    """
    fvg_t = next_unfilled_fvg_target(h1_fvg, entry_time, entry_price, side, lookback_bars=lookback_bars)
    if fvg_t is not None:
        return fvg_t, "fvg_h1"

    if m5_row.get("regime_vol") == "baja":
        day_t = m5_row.get("day_lo") if side == "short" else m5_row.get("day_hi")
        if pd.notna(day_t):
            day_t = float(day_t)
            if (side == "short" and day_t < entry_price) or (side == "long" and day_t > entry_price):
                return day_t, "day_range"

    swing_t = m5_row.get("last_swing_low") if side == "short" else m5_row.get("last_swing_high")
    if pd.notna(swing_t):
        swing_t = float(swing_t)
        if (side == "short" and swing_t < entry_price) or (side == "long" and swing_t > entry_price):
            return swing_t, "swing_opposite"

    return None, "none"


def resolve_target_v7(
    *,
    h1_fvg: pd.DataFrame,
    m5_row,
    entry_time: pd.Timestamp,
    entry_price: float,
    side: str,
    lookback_bars: int = 30,
    quarter_step: float = 0.0025,
    quarter_n_levels: int = 1,
) -> tuple[float | None, str]:
    """Jerarquía de salida ADR-015: igual que `resolve_target` (V5/ADR-011), pero
    inserta el nivel de Quarter Theory como prioridad 2 (entre FVG H1 y el rango
    del día), reflejando "Targets: BOS, Quarter levels" de la jerarquía
    discrecional completa del usuario. `swing_opposite` (última prioridad) ES el
    BOS: el swing opuesto confirmado que el precio tendría que romper (Break of
    Structure) para llegar ahí.

    NO modifica `resolve_target` (V5 queda intacto y comparable, sección 16).

    Prioridades, en orden, se detiene en la primera que aplica:
        1. FVG en H1 sin rellenar (idéntico a V5).
        2. Cuarto (.00/.25/.50/.75) inmediato en la dirección del trade
           (`features.quarter_theory.quarter_target`) — NUEVO en ADR-015.
        3. Extremo del día si `regime_vol == 'baja'` (idéntico a V5).
        4. Swing opuesto confirmado = BOS (idéntico a V5, última prioridad).
    """
    fvg_t = next_unfilled_fvg_target(h1_fvg, entry_time, entry_price, side, lookback_bars=lookback_bars)
    if fvg_t is not None:
        return fvg_t, "fvg_h1"

    from features.quarter_theory import quarter_target  # import local: evita ciclo a nivel de módulo
    q_t = quarter_target(entry_price, side, step=quarter_step, n_levels=quarter_n_levels)
    if (side == "long" and q_t > entry_price) or (side == "short" and q_t < entry_price):
        return q_t, "quarter_level"

    if m5_row.get("regime_vol") == "baja":
        day_t = m5_row.get("day_lo") if side == "short" else m5_row.get("day_hi")
        if pd.notna(day_t):
            day_t = float(day_t)
            if (side == "short" and day_t < entry_price) or (side == "long" and day_t > entry_price):
                return day_t, "day_range"

    swing_t = m5_row.get("last_swing_low") if side == "short" else m5_row.get("last_swing_high")
    if pd.notna(swing_t):
        swing_t = float(swing_t)
        if (side == "short" and swing_t < entry_price) or (side == "long" and swing_t > entry_price):
            return swing_t, "bos_swing_opposite"

    return None, "none"
