"""Niveles de referencia para la hipótesis ADR-007: PDH/PDL y high/low de Tokio.

Point-in-time estricto:
  - PDH/PDL usan SOLO el día calendario anterior (UTC); el high/low del día en curso
    NUNCA se filtra hacia atrás.
  - El high/low de la sesión de Tokio es acumulado (expanding) DENTRO de la sesión
    en curso: en la barra t solo incorpora barras de la misma sesión hasta t.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema


def add_pdh_pdl(intraday: pd.DataFrame, d1: pd.DataFrame) -> pd.DataFrame:
    """Añade `pdh` / `pdl` (máximo/mínimo del día calendario anterior, UTC).

    Args:
        intraday: DataFrame intradía (M5/H1) con índice UTC.
        d1: DataFrame D1 del mismo símbolo (índice a 00:00 UTC de cada día).

    Returns:
        Copia de `intraday` con columnas `pdh`, `pdl`.
    """
    # Valor del día anterior, ubicado en el timestamp del día actual (shift(1)).
    prev = pd.DataFrame({
        "pdh": d1[schema.HIGH].shift(1),
        "pdl": d1[schema.LOW].shift(1),
    }).dropna()
    prev.index = prev.index.normalize()

    out = intraday.copy()
    day = out.index.normalize()
    out["pdh"] = pd.Series(day, index=out.index).map(prev["pdh"]).to_numpy()
    out["pdl"] = pd.Series(day, index=out.index).map(prev["pdl"]).to_numpy()
    return out


def add_tokyo_session_levels(intraday: pd.DataFrame, *, in_tokyo_col: str = "in_tokyo") -> pd.DataFrame:
    """Añade `tokyo_hi` / `tokyo_lo`: máximo/mínimo acumulado de la sesión de Tokio.

    Requiere la columna booleana `in_tokyo` (features/sessions.add_sessions). Fuera
    de la sesión de Tokio las columnas quedan NaN. Dentro, es expanding (PIT).
    """
    out = intraday.copy()
    if in_tokyo_col not in out.columns:
        raise ValueError(f"Falta la columna {in_tokyo_col!r} (añade sesiones primero)")

    in_tok = out[in_tokyo_col].to_numpy()
    # Nueva sesión cada vez que in_tokyo pasa de False a True.
    start = in_tok & ~np.r_[False, in_tok[:-1]]
    session_id = np.cumsum(start)

    high = out[schema.HIGH].to_numpy()
    low = out[schema.LOW].to_numpy()
    tok_hi = np.full(len(out), np.nan)
    tok_lo = np.full(len(out), np.nan)

    cur_id = -1
    cmax = -np.inf
    cmin = np.inf
    for t in range(len(out)):
        if not in_tok[t]:
            continue
        if session_id[t] != cur_id:
            cur_id = session_id[t]
            cmax, cmin = -np.inf, np.inf
        cmax = max(cmax, high[t])
        cmin = min(cmin, low[t])
        tok_hi[t] = cmax
        tok_lo[t] = cmin

    out["tokyo_hi"] = tok_hi
    out["tokyo_lo"] = tok_lo
    return out


def add_pwh_pwl(intraday: pd.DataFrame, d1: pd.DataFrame) -> pd.DataFrame:
    """Añade `pwh` / `pwl`: máximo/mínimo de la semana calendario ANTERIOR (ADR-008).

    Point-in-time: cada barra recibe el extremo de la semana previa completa; la
    semana en curso nunca se filtra hacia atrás.
    """
    iso = d1.index.isocalendar()
    wk = (iso["year"].astype(int) * 100 + iso["week"].astype(int)).to_numpy()
    wk_high = pd.Series(d1[schema.HIGH].to_numpy()).groupby(wk).max()
    wk_low = pd.Series(d1[schema.LOW].to_numpy()).groupby(wk).min()
    order = list(wk_high.index)
    prev_high = {w: (wk_high[order[i - 1]] if i > 0 else float("nan"))
                 for i, w in enumerate(order)}
    prev_low = {w: (wk_low[order[i - 1]] if i > 0 else float("nan"))
                for i, w in enumerate(order)}

    out = intraday.copy()
    iso_i = out.index.isocalendar()
    wk_i = (iso_i["year"].astype(int) * 100 + iso_i["week"].astype(int)).to_numpy()
    out["pwh"] = [prev_high.get(w, float("nan")) for w in wk_i]
    out["pwl"] = [prev_low.get(w, float("nan")) for w in wk_i]
    return out


def add_equal_levels(
    df: pd.DataFrame,
    *,
    atr_col: str = "atr",
    tol_atr_frac: float = 0.1,
    lookback: int = 50,
) -> pd.DataFrame:
    """Marca equal highs/lows: ≥2 swings confirmados dentro de `tol_atr_frac`×ATR (ADR-008).

    Requiere `swing_high_confirmed`/`swing_low_confirmed` y `last_swing_high/low`
    (features/structure) y un ATR (`atr_col`). Point-in-time: usa solo swings ya
    confirmados dentro de la ventana de lookback.

    Añade: equal_high, equal_low (bool) en la barra donde se confirma el 2º swing igual.
    """
    out = df.copy()
    n = len(out)
    atr = out[atr_col].to_numpy() if atr_col in out.columns else np.full(n, np.nan)

    def _equal(conf_col, price_col):
        conf = out[conf_col].to_numpy()
        price = out[price_col].to_numpy()  # precio del último swing confirmado (ffill)
        flag = np.zeros(n, dtype=bool)
        recent: list[tuple[int, float]] = []  # (idx, precio del swing)
        for t in range(n):
            if conf[t] and not np.isnan(price[t]):
                p = price[t]
                tol = (tol_atr_frac * atr[t]) if not np.isnan(atr[t]) else 0.0
                recent = [(i, q) for i, q in recent if t - i <= lookback]
                if any(abs(p - q) <= tol for _, q in recent):
                    flag[t] = True
                recent.append((t, p))
        return flag

    out["equal_high"] = _equal("swing_high_confirmed", "last_swing_high")
    out["equal_low"] = _equal("swing_low_confirmed", "last_swing_low")
    return out


def add_recent_equal_flag(
    m5: pd.DataFrame,
    *,
    window_start_hour_utc: int = 22,
    entry_session_end_hour_utc: int = 4,
) -> pd.DataFrame:
    """Marca `equal_high_recent` / `equal_low_recent` (ADR-011): True desde que un
    `equal_high`/`equal_low` se formó dentro de la ventana [22:00 UTC del día
    anterior, 04:00 UTC del día en curso) hasta el cierre de esa ventana.

    La ventana cruza medianoche por diseño (arranca 2h antes de la sesión de
    Tokio para capturar equals formados "un poco antes", según lo pedido). El
    estado se reinicia en cada nuevo ciclo de ventana (no se arrastra de un día
    al siguiente). Point-in-time: en la barra t solo refleja equals ya
    confirmados hasta t (reutiliza `equal_high`/`equal_low` de
    `features.levels.add_equal_levels`, que ya es PIT).
    """
    out = m5.copy()
    hour = out.index.hour
    active = (hour >= window_start_hour_utc) | (hour < entry_session_end_hour_utc)
    eqh = out["equal_high"].to_numpy() if "equal_high" in out.columns else None
    eql = out["equal_low"].to_numpy() if "equal_low" in out.columns else None
    n = len(out)
    recent_h = np.zeros(n, dtype=bool)
    recent_l = np.zeros(n, dtype=bool)
    state_h, state_l = False, False
    was_active = False
    for t in range(n):
        if active[t] and not was_active:
            state_h, state_l = False, False  # nuevo ciclo de ventana (reinicia)
        if active[t]:
            if eqh is not None:
                state_h = state_h or bool(eqh[t])
            if eql is not None:
                state_l = state_l or bool(eql[t])
            recent_h[t] = state_h
            recent_l[t] = state_l
        was_active = active[t]
    out["equal_high_recent"] = recent_h
    out["equal_low_recent"] = recent_l
    return out


def add_day_extremes(intraday: pd.DataFrame) -> pd.DataFrame:
    """Añade `day_hi` / `day_lo`: máximo/mínimo acumulado del día calendario UTC
    en curso (ADR-011, salida jerárquica "próximo punto de liquidez", prioridad 2).

    Point-in-time: en la barra t solo incorpora barras del MISMO día calendario
    UTC hasta t (expanding, se reinicia en cada cambio de día — nunca usa datos
    futuros del mismo día ni de otro día).
    """
    out = intraday.copy()
    day = out.index.normalize().to_numpy()
    high = out[schema.HIGH].to_numpy()
    low = out[schema.LOW].to_numpy()
    n = len(out)
    day_hi = np.full(n, np.nan)
    day_lo = np.full(n, np.nan)
    cur_day = None
    cmax, cmin = -np.inf, np.inf
    for t in range(n):
        if day[t] != cur_day:
            cur_day = day[t]
            cmax, cmin = -np.inf, np.inf
        cmax = max(cmax, high[t])
        cmin = min(cmin, low[t])
        day_hi[t] = cmax
        day_lo[t] = cmin
    out["day_hi"] = day_hi
    out["day_lo"] = day_lo
    return out


def add_accumulation_range(
    df: pd.DataFrame,
    *,
    regime_vol_col: str = "regime_vol",
    regime_trend_col: str = "regime_trend",
    window: int = 6,
) -> pd.DataFrame:
    """Marca acumulación: `window` velas consecutivas de baja volatilidad / rango.

    Precondición dura de V2 (ADR-008). Una barra t está "en acumulación" si las
    `window` barras que terminan en t tienen todas regime_vol='baja' o
    regime_trend='range'. El rango = [min low, max high] de esa ventana.

    Añade: in_accumulation (bool), acc_low, acc_high (float, NaN si no acumula).
    Point-in-time: la ventana es trailing (solo pasado, incluye t).
    """
    out = df.copy()
    n = len(out)
    vol = out[regime_vol_col].to_numpy() if regime_vol_col in out.columns else np.full(n, None)
    trend = out[regime_trend_col].to_numpy() if regime_trend_col in out.columns else np.full(n, None)
    high = out[schema.HIGH].to_numpy()
    low = out[schema.LOW].to_numpy()

    calm = np.array([(v == "baja") or (tr == "range") for v, tr in zip(vol, trend)], dtype=bool)
    in_acc = np.zeros(n, dtype=bool)
    acc_low = np.full(n, np.nan)
    acc_high = np.full(n, np.nan)
    for t in range(window - 1, n):
        if calm[t - window + 1: t + 1].all():
            in_acc[t] = True
            acc_low[t] = low[t - window + 1: t + 1].min()
            acc_high[t] = high[t - window + 1: t + 1].max()

    out["in_accumulation"] = in_acc
    out["acc_low"] = acc_low
    out["acc_high"] = acc_high
    return out
