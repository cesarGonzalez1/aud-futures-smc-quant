"""Hipótesis de estrategia V1: liquidity sweep + Inverse FVG (ADR-007).

Pipeline: bias del día (régimen D1) → sweep H1 alineado al bias sobre PDH/PDL o
high/low de Tokio → confirmación IFVG en M5 dentro de una ventana → entrada en la
apertura de la barra M5 siguiente a la confirmación → stop tras la mecha del sweep
→ target en el swing opuesto H1. Una posición a la vez.

Produce una lista de operaciones simuladas (no una curva de equity todavía). El
backtest con costos y métricas por cohorte usa esta lista (ver `backtest/`).

Point-in-time: la entrada usa la APERTURA de la barra posterior a la confirmación
(nunca el cierre de la barra que confirma). El sweep y el IFVG usan solo datos ≤ t.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

from analysis.regime import add_trend_regime
from data import schema


@dataclass
class Trade:
    """Una operación simulada (sin costos; los costos se aplican en el backtest)."""
    entry_time: str
    side: str            # "long" | "short"
    entry_price: float
    stop: float
    target: float
    exit_time: str
    exit_price: float
    outcome: str         # "target" | "stop" | "open"
    r_multiple: float
    cohort: str


def daily_bias_from_d1(d1: pd.DataFrame) -> pd.Series:
    """Bias por día a partir del régimen de tendencia D1 del día ANTERIOR (ADR-007).

    Requiere que `d1` tenga `adx` y `ema_trend` (indicadores sobre D1). Devuelve una
    Serie indexada por día (normalizado) con valores {-1, 0, +1}: el bias a USAR ese
    día proviene del cierre del día previo (shift(1)).
    """
    reg = add_trend_regime(d1)
    slope = d1["ema_trend"].diff()
    bias = pd.Series(0, index=d1.index, dtype=int)
    bias[(reg["regime_trend"] == "trending") & (slope > 0)] = 1
    bias[(reg["regime_trend"] == "trending") & (slope < 0)] = -1
    prev = bias.shift(1).fillna(0).astype(int)
    prev.index = prev.index.normalize()
    return prev


def _sweep_at(row, bias: int) -> bool:
    """¿La barra H1 hace un sweep de un nivel alineado al bias? (ADR-004 + ADR-007)."""
    if bias == -1:  # bajista -> sweep de máximos (penetra y cierra por debajo)
        for lvl in (row.get("pdh"), row.get("tokyo_hi")):
            if pd.notna(lvl) and row[schema.HIGH] > lvl and row[schema.CLOSE] < lvl:
                return True
    elif bias == 1:  # alcista -> sweep de mínimos
        for lvl in (row.get("pdl"), row.get("tokyo_lo")):
            if pd.notna(lvl) and row[schema.LOW] < lvl and row[schema.CLOSE] > lvl:
                return True
    return False


def _simulate_exit(m5: pd.DataFrame, entry_pos: int, side: str, stop: float, target: float):
    """Simula la salida barra a barra en M5 desde `entry_pos`. Stop se evalúa antes."""
    h = m5[schema.HIGH].to_numpy()
    l = m5[schema.LOW].to_numpy()
    idx = m5.index
    for p in range(entry_pos, len(m5)):
        if side == "short":
            if h[p] >= stop:
                return idx[p].isoformat(), stop, "stop"
            if l[p] <= target:
                return idx[p].isoformat(), target, "target"
        else:
            if l[p] <= stop:
                return idx[p].isoformat(), stop, "stop"
            if h[p] >= target:
                return idx[p].isoformat(), target, "target"
    return idx[-1].isoformat(), float(m5[schema.CLOSE].iloc[-1]), "open"


def generate_trades(
    h1: pd.DataFrame,
    m5: pd.DataFrame,
    daily_bias: pd.Series,
    *,
    window_start: int = 0,
    window_end: int = 4,
    confirm_lookback_m5: int = 12,
    stop_buffer: float = 0.0,
) -> list[Trade]:
    """Genera operaciones según ADR-007.

    Args:
        h1: H1 con columnas high/low/close, pdh, pdl, tokyo_hi, tokyo_lo,
            last_swing_high, last_swing_low.
        m5: M5 con open/high/low/close, ifvg_bull, ifvg_bear.
        daily_bias: salida de `daily_bias_from_d1` (indexada por día).
        window_start/window_end: ventana horaria UTC de la sesión (default 00-04).
        confirm_lookback_m5: barras M5 tras el sweep para buscar el IFVG (default 12).
        stop_buffer: colchón añadido más allá de la mecha del sweep.
    """
    trades: list[Trade] = []
    freq_m5 = pd.Timedelta(schema.freq_for("M5"))
    freq_h1 = pd.Timedelta(schema.freq_for("H1"))
    open_until: pd.Timestamp | None = None

    in_window = (h1.index.hour >= window_start) & (h1.index.hour < window_end)
    for j in h1.index[in_window]:
        if open_until is not None and j <= open_until:
            continue  # una posición a la vez
        bias = int(daily_bias.get(j.normalize(), 0))
        if bias == 0:
            continue
        row = h1.loc[j]
        if not _sweep_at(row, bias):
            continue

        # Ventana M5 tras el cierre de la barra H1 del sweep.
        start = j + freq_h1
        end = start + confirm_lookback_m5 * freq_m5
        win = m5[(m5.index >= start) & (m5.index < end)]
        sig_col = "ifvg_bear" if bias == -1 else "ifvg_bull"
        conf = win.index[win[sig_col]] if sig_col in win.columns else []
        if len(conf) == 0:
            continue
        conf_bar = conf[0]
        pos = m5.index.get_loc(conf_bar)
        if pos + 1 >= len(m5):
            continue

        entry_pos = pos + 1
        entry_time = m5.index[entry_pos]
        entry_price = float(m5[schema.OPEN].iloc[entry_pos])
        side = "short" if bias == -1 else "long"
        if side == "short":
            stop = float(row[schema.HIGH]) + stop_buffer
            target = row.get("last_swing_low")
            if pd.isna(target) or not (target < entry_price):
                continue
        else:
            stop = float(row[schema.LOW]) - stop_buffer
            target = row.get("last_swing_high")
            if pd.isna(target) or not (target > entry_price):
                continue
        target = float(target)

        exit_time, exit_price, outcome = _simulate_exit(m5, entry_pos, side, stop, target)
        risk = abs(entry_price - stop)
        r = ((exit_price - entry_price) if side == "long" else (entry_price - exit_price))
        r_mult = r / risk if risk > 0 else 0.0
        trades.append(Trade(
            entry_time=entry_time.isoformat(), side=side, entry_price=entry_price,
            stop=stop, target=target, exit_time=exit_time, exit_price=exit_price,
            outcome=outcome, r_multiple=r_mult, cohort=str(entry_time.year),
        ))
        open_until = pd.Timestamp(exit_time)

    return trades


def trades_to_frame(trades: list[Trade]) -> pd.DataFrame:
    """Convierte la lista de operaciones a DataFrame."""
    return pd.DataFrame([asdict(t) for t in trades])
