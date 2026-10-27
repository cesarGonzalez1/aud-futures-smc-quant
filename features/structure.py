"""Estructura de mercado: swings y liquidity sweeps (ADR-004).

Definiciones formales (ADR-004, defaults configurables):
  - **Swing high**: barra `i` cuyo `high[i]` es el máximo ESTRICTO en la ventana
    `[i-k, i+k]`, con `k=2` (fractal de 5 barras). Swing low: simétrico sobre `low`.
  - **Liquidity sweep** sobre un swing high de precio `P`: en la barra `j`,
    `high[j] > P` (penetra), `close[j] < P` (rechazo), y `P` se formó dentro de las
    últimas `sweep_lookback=50` barras. Simétrico para swing lows.

**Corrección crítica de look-ahead (no está en el texto de ADR-004 pero es
obligatoria por la sección 6.1):** un swing centrado en `i` solo puede CONFIRMARSE
`k` barras después (en `i+k`), porque necesita las `k` barras posteriores. Por eso
este módulo NO expone el flag centrado como feature directo; expone versiones
point-in-time confirmadas con retraso `k`:
  - `swing_high_confirmed[j]` = la barra `j-k` resultó ser swing high (conocible en `j`).
  - `last_swing_high[j]`      = precio del último swing high confirmado hasta `j`.
  - `liquidity_sweep_high[j]` = ocurrió un sweep en `j` (usa solo swings ya confirmados).
Así el test anti-look-ahead (6.1) pasa: el valor en `t` no cambia al recalcular
sobre la serie recortada `[:t]`.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema


def _strict_extrema(values: np.ndarray, k: int, kind: str) -> np.ndarray:
    """Marca extremos estrictos centrados (swing crudo, NO point-in-time todavía).

    Args:
        values: serie de `high` (kind='high') o `low` (kind='low').
        k: mitad de la ventana fractal.
        kind: 'high' o 'low'.

    Returns:
        Array booleano: True en el índice `i` si es extremo estricto en [i-k, i+k].
    """
    n = len(values)
    flag = np.zeros(n, dtype=bool)
    for i in range(k, n - k):
        center = values[i]
        neighbors = np.concatenate([values[i - k:i], values[i + 1:i + k + 1]])
        if kind == "high":
            flag[i] = center > neighbors.max()
        else:
            flag[i] = center < neighbors.min()
    return flag


def add_structure(
    df: pd.DataFrame,
    *,
    k: int = 2,
    sweep_lookback: int = 50,
) -> pd.DataFrame:
    """Añade columnas point-in-time de swings y liquidity sweeps (ADR-004).

    Columnas añadidas:
        swing_high_confirmed, swing_low_confirmed  (bool)
        last_swing_high, last_swing_low            (float, precio ffill)
        liquidity_sweep_high, liquidity_sweep_low  (bool)
    """
    out = df.copy()
    high = out[schema.HIGH].to_numpy()
    low = out[schema.LOW].to_numpy()
    close = out[schema.CLOSE].to_numpy()
    n = len(out)

    raw_sh = _strict_extrema(high, k, "high")
    raw_sl = _strict_extrema(low, k, "low")

    # Confirmación con retraso k: el swing en i se conoce en i+k.
    conf_sh = np.zeros(n, dtype=bool)
    conf_sl = np.zeros(n, dtype=bool)
    conf_sh[k:] = raw_sh[:-k] if k > 0 else raw_sh
    conf_sl[k:] = raw_sl[:-k] if k > 0 else raw_sl

    # Precio e índice de formación del último swing confirmado, hasta cada barra j.
    last_high_price = np.full(n, np.nan)
    last_high_form = np.full(n, -1, dtype=int)  # índice i donde se formó
    last_low_price = np.full(n, np.nan)
    last_low_form = np.full(n, -1, dtype=int)

    cur_hp, cur_hf = np.nan, -1
    cur_lp, cur_lf = np.nan, -1
    for j in range(n):
        if conf_sh[j]:            # la barra j-k es swing high
            cur_hp, cur_hf = high[j - k], j - k
        if conf_sl[j]:
            cur_lp, cur_lf = low[j - k], j - k
        last_high_price[j], last_high_form[j] = cur_hp, cur_hf
        last_low_price[j], last_low_form[j] = cur_lp, cur_lf

    # Sweeps: usan solo el último swing confirmado y reciente (<= sweep_lookback).
    sweep_high = np.zeros(n, dtype=bool)
    sweep_low = np.zeros(n, dtype=bool)
    for j in range(n):
        P = last_high_price[j]
        if not np.isnan(P) and (j - last_high_form[j]) <= sweep_lookback:
            sweep_high[j] = (high[j] > P) and (close[j] < P)
        Q = last_low_price[j]
        if not np.isnan(Q) and (j - last_low_form[j]) <= sweep_lookback:
            sweep_low[j] = (low[j] < Q) and (close[j] > Q)

    out["swing_high_confirmed"] = conf_sh
    out["swing_low_confirmed"] = conf_sl
    out["last_swing_high"] = last_high_price
    out["last_swing_low"] = last_low_price
    out["liquidity_sweep_high"] = sweep_high
    out["liquidity_sweep_low"] = sweep_low
    return out


def add_order_blocks(
    df: pd.DataFrame,
    *,
    atr_col: str = "atr",
    displacement_bars: int = 3,
    displacement_atr: float = 1.5,
) -> pd.DataFrame:
    """Detecta order blocks y su mitigación (ADR-004 anexo / ADR-008).

    Desplazamiento: `displacement_bars` velas consecutivas con rango acumulado
    ≥ `displacement_atr`×ATR que rompen el swing opuesto más reciente. El OB es la
    última vela de color contrario antes de la primera vela del desplazamiento; su
    zona es [low, high] de esa vela. Un OB se marca mitigado la primera vez que un
    cierre posterior lo atraviesa.

    Requiere `atr`, `last_swing_high`, `last_swing_low` (structure). Point-in-time:
    el desplazamiento se confirma en su última vela; el OB (anterior) se conoce ahí.

    Añade: ob_bull, ob_bear (bool, en la vela OB), ob_bull_low/high, ob_bear_low/high
    (float, zona vigente hasta mitigación; NaN cuando no hay OB vigente en esa barra).
    """
    out = df.copy()
    n = len(out)
    o = out[schema.OPEN].to_numpy()
    h = out[schema.HIGH].to_numpy()
    low = out[schema.LOW].to_numpy()
    c = out[schema.CLOSE].to_numpy()
    atr = out[atr_col].to_numpy() if atr_col in out.columns else np.full(n, np.nan)
    sh = out["last_swing_high"].to_numpy()
    sl = out["last_swing_low"].to_numpy()

    ob_bull = np.zeros(n, dtype=bool)
    ob_bear = np.zeros(n, dtype=bool)
    d = displacement_bars

    for t in range(d, n):
        rng = h[t - d + 1: t + 1].max() - low[t - d + 1: t + 1].min()
        thr = displacement_atr * atr[t] if not np.isnan(atr[t]) else np.inf
        if rng < thr:
            continue
        first = t - d + 1  # primera vela del desplazamiento
        # Alcista: rompe el swing high previo -> OB = última vela bajista antes de `first`.
        if not np.isnan(sh[first]) and c[t] > sh[first]:
            for b in range(first - 1, max(first - 10, -1), -1):
                if c[b] < o[b]:
                    ob_bull[b] = True
                    break
        # Bajista: rompe el swing low previo -> OB = última vela alcista antes de `first`.
        elif not np.isnan(sl[first]) and c[t] < sl[first]:
            for b in range(first - 1, max(first - 10, -1), -1):
                if c[b] > o[b]:
                    ob_bear[b] = True
                    break

    # Zonas vigentes con mitigación (primer cierre que atraviesa invalida).
    def _live_zones(flag, side):
        lo_out = np.full(n, np.nan)
        hi_out = np.full(n, np.nan)
        active: list[tuple[float, float]] = []
        for t in range(n):
            if flag[t]:
                active.append((low[t], h[t]))
            still = []
            for zlo, zhi in active:
                mitigated = (c[t] < zlo) if side == "bull" else (c[t] > zhi)
                if not mitigated:
                    still.append((zlo, zhi))
            active = still
            if active:  # zona más reciente vigente
                lo_out[t], hi_out[t] = active[-1]
        return lo_out, hi_out

    out["ob_bull"] = ob_bull
    out["ob_bear"] = ob_bear
    out["ob_bull_low"], out["ob_bull_high"] = _live_zones(ob_bull, "bull")
    out["ob_bear_low"], out["ob_bear_high"] = _live_zones(ob_bear, "bear")
    return out
