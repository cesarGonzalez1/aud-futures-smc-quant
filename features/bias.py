"""Bias por estructura de mercado, multi-timeframe y multi-sesión (ADR-011).

Reemplaza, para la hipótesis V5, el bias basado en régimen ADX/EMA (ADR-007) por
bias basado en ESTRUCTURA de swings — más cercano a como el usuario lo define:

    - alcista (+1): secuencia de los últimos 2 swings confirmados es
      higher-high Y higher-low.
    - bajista (-1): lower-high Y lower-low.
    - neutral (0): estructura mixta, o aún no hay 2 swings confirmados de cada lado.

Cuatro fuentes de bias, todas reducidas a la misma escala (-1/0/+1):
    - D1: estructura sobre velas D1 completas.
    - H4: estructura sobre velas H1 agregadas a 4H.
    - NY AM / NY PM: estructura calculada de forma AISLADA por sesión y día
      calendario UTC, usando M5 solo dentro de esa ventana horaria (sin arrastrar
      estado de otros días ni de otras sesiones) — ventanas fijas en UTC porque
      corresponden al horario del usuario en CDMX (UTC-6, sin DST desde 2022), no
      al horario de la plaza de Nueva York.

Todo es point-in-time: cada fuente solo usa datos con timestamp estrictamente
anterior a las 00:00 UTC del día de trading que va a operar (sección 6.1).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features import structure


def add_structure_bias(df: pd.DataFrame) -> pd.DataFrame:
    """Añade `structure_bias` a partir de columnas ya calculadas por
    `features.structure.add_structure` (swing_high_confirmed, swing_low_confirmed,
    last_swing_high, last_swing_low).

    El estado se actualiza únicamente cuando se confirma un swing nuevo (de
    cualquier lado) y persiste entre confirmaciones — igual que la lectura de
    estructura de mercado de un trader, que no "olvida" el bias entre swings.
    Requiere al menos 2 swings confirmados de cada lado antes de emitir ±1; antes
    de eso el bias es 0 (neutral, sin evidencia suficiente).
    """
    out = df.copy()
    n = len(out)
    conf_sh = out["swing_high_confirmed"].to_numpy()
    conf_sl = out["swing_low_confirmed"].to_numpy()
    lsh = out["last_swing_high"].to_numpy()
    lsl = out["last_swing_low"].to_numpy()

    bias = np.zeros(n, dtype=int)
    highs_seen: list[float] = []
    lows_seen: list[float] = []
    state = 0
    for t in range(n):
        if conf_sh[t] and not np.isnan(lsh[t]):
            highs_seen.append(float(lsh[t]))
            if len(highs_seen) > 2:
                highs_seen.pop(0)
        if conf_sl[t] and not np.isnan(lsl[t]):
            lows_seen.append(float(lsl[t]))
            if len(lows_seen) > 2:
                lows_seen.pop(0)
        if len(highs_seen) == 2 and len(lows_seen) == 2:
            higher_high = highs_seen[-1] > highs_seen[-2]
            higher_low = lows_seen[-1] > lows_seen[-2]
            lower_high = highs_seen[-1] < highs_seen[-2]
            lower_low = lows_seen[-1] < lows_seen[-2]
            if higher_high and higher_low:
                state = 1
            elif lower_high and lower_low:
                state = -1
            else:
                state = 0
        bias[t] = state
    out["structure_bias"] = bias
    return out


def resample_h4(h1: pd.DataFrame) -> pd.DataFrame:
    """Agrega H1 a barras de 4 horas (contexto de bias, ADR-011). No es ingesta
    nueva: se deriva del H1 ya validado."""
    agg = {schema.OPEN: "first", schema.HIGH: "max", schema.LOW: "min", schema.CLOSE: "last"}
    if schema.VOLUME in h1.columns:
        agg[schema.VOLUME] = "sum"
    if schema.SPREAD in h1.columns:
        agg[schema.SPREAD] = "mean"
    out = h1.resample("4h", label="left", closed="left").agg(agg)
    out = out.dropna(subset=[schema.OPEN])
    out.index.name = h1.index.name
    return out


def bias_known_before_day(bias_series: pd.Series) -> pd.Series:
    """Convierte una serie de bias indexada por barra en una serie por DÍA
    CALENDARIO (UTC), con el último valor confirmado ESTRICTAMENTE ANTES de las
    00:00 UTC de ese día (point-in-time, vía merge_asof backward).
    """
    if bias_series.empty:
        return pd.Series(dtype=int)
    days = pd.DatetimeIndex(sorted(pd.unique(bias_series.index.normalize())))
    right = bias_series.rename("bias").reset_index()
    right.columns = ["ts", "bias"]
    # Resta 1 microsegundo (no nanosegundo) para no forzar un upcast de resolución
    # del dtype datetime al mezclar con el índice original (evita MergeError por
    # dtype mismatch ns vs us); se castea explícitamente al dtype de `ts`.
    left = pd.DataFrame({"day": days})
    left["asof_ts"] = (left["day"] - pd.Timedelta(microseconds=1)).astype(right["ts"].dtype)
    merged = pd.merge_asof(
        left.sort_values("asof_ts"), right.sort_values("ts"),
        left_on="asof_ts", right_on="ts", direction="backward",
    )
    merged["bias"] = merged["bias"].fillna(0).astype(int)
    return pd.Series(merged["bias"].to_numpy(), index=merged["day"]).sort_index()


def session_structure_bias(
    intraday: pd.DataFrame,
    *,
    start_hour_utc: int,
    end_hour_utc: int,
    k: int = 2,
) -> pd.Series:
    """Bias de estructura calculado de forma AISLADA por sesión y día calendario
    UTC (ADR-011): para cada día, usa solo las barras dentro de
    [start_hour_utc, end_hour_utc) de ESE día (sin cruzar medianoche, sin arrastrar
    estado de otros días), calcula swings/estructura únicamente sobre ese tramo, y
    toma el bias resultante al cierre de la ventana.

    Devuelve una Serie indexada por día calendario (normalizado) = el día en que
    ocurrió la sesión (no el día de trading que la va a usar; ese mapeo lo hace
    quien llama, vía `bias_known_before_day` o desplazando el índice).
    """
    hours = intraday.index.hour
    days = intraday.index.normalize()
    out: dict[pd.Timestamp, int] = {}
    for day in pd.unique(days):
        mask = (days == day) & (hours >= start_hour_utc) & (hours < end_hour_utc)
        sub = intraday.loc[mask]
        if len(sub) < (2 * k + 1):
            out[day] = 0
            continue
        s = structure.add_structure(sub, k=k)
        s = add_structure_bias(s)
        out[day] = int(s["structure_bias"].iloc[-1])
    return pd.Series(out).sort_index()


def combine_bias(d1: int, h4: int, ny_am: int, ny_pm: int) -> tuple[int, str]:
    """Regla de confluencia (ADR-011):
        3+ fuentes alineadas               -> operar, confianza 'alta'.
        2 alineadas y las otras 2 NEUTRALES (ninguna opuesta) -> operar, 'baja'.
        cualquier otro caso (2v2, opuestas, etc.) -> no operar (dirección 0).
    """
    votes = [d1, h4, ny_am, ny_pm]
    bulls = votes.count(1)
    bears = votes.count(-1)
    if bulls >= 3:
        return 1, "alta"
    if bears >= 3:
        return -1, "alta"
    if bulls == 2 and bears == 0:
        return 1, "baja"
    if bears == 2 and bulls == 0:
        return -1, "baja"
    return 0, "na"


def build_daily_confluence(
    d1: pd.DataFrame,
    h1: pd.DataFrame,
    m5: pd.DataFrame,
    *,
    ny_am_hours: tuple[int, int],
    ny_pm_hours: tuple[int, int],
) -> pd.DataFrame:
    """Orquesta las 4 fuentes de bias y arma la tabla de confluencia por día de
    trading (ADR-011).

    `d1`/`h1` deben traer ya `swing_high_confirmed`/`swing_low_confirmed`/
    `last_swing_high`/`last_swing_low` (features.structure.add_structure). `m5`
    debe traerlas también, para las ventanas de sesión NY AM/PM.

    Las sesiones NY AM/PM ocurren en el día calendario D-1 respecto al día de
    trading D (que opera en la sesión de Tokio, 00:00-04:00 UTC de D) — se
    desplaza el índice +1 día para alinearlas al día de trading que las va a usar.

    Returns:
        DataFrame indexado por día de trading (UTC, normalizado) con columnas
        `d1`, `h4`, `ny_am`, `ny_pm` (cada una -1/0/+1) y `direction`/`confidence`
        (salida de `combine_bias`).
    """
    d1_bias = add_structure_bias(d1)["structure_bias"]
    d1_by_day = bias_known_before_day(d1_bias)

    h4 = resample_h4(h1)
    h4 = structure.add_structure(h4)
    h4_bias = add_structure_bias(h4)["structure_bias"]
    h4_by_day = bias_known_before_day(h4_bias)

    ny_am_raw = session_structure_bias(m5, start_hour_utc=ny_am_hours[0], end_hour_utc=ny_am_hours[1])
    ny_pm_raw = session_structure_bias(m5, start_hour_utc=ny_pm_hours[0], end_hour_utc=ny_pm_hours[1])
    # Desplazar +1 día: la sesión del día D-1 es la que "conoce" el día de trading D.
    ny_am_by_day = ny_am_raw.copy()
    ny_am_by_day.index = ny_am_by_day.index + pd.Timedelta(days=1)
    ny_pm_by_day = ny_pm_raw.copy()
    ny_pm_by_day.index = ny_pm_by_day.index + pd.Timedelta(days=1)

    all_days = sorted(set(d1_by_day.index) | set(h4_by_day.index)
                       | set(ny_am_by_day.index) | set(ny_pm_by_day.index))
    rows = []
    for day in all_days:
        d = int(d1_by_day.get(day, 0))
        h = int(h4_by_day.get(day, 0))
        am = int(ny_am_by_day.get(day, 0))
        pm = int(ny_pm_by_day.get(day, 0))
        direction, confidence = combine_bias(d, h, am, pm)
        rows.append({"day": day, "d1": d, "h4": h, "ny_am": am, "ny_pm": pm,
                     "direction": direction, "confidence": confidence})
    return pd.DataFrame(rows).set_index("day").sort_index()
