"""Hipótesis V3: mecánica AMD recalculada en M5 (ADR-009), contexto en H1/D1.

Extiende V2 (`liquidity_sweep_ifvg_v2.py`, intacto y comparable). Diferencia
central: TODA la mecánica de estructura (swing, sweep, order block, acumulación,
equal highs/lows) y la confirmación IFVG ocurren en el MISMO timeframe M5. El bias
del día sigue leyéndose de D1 (contexto), sin cambio (ADR-009).

A diferencia de V2 (sweep en H1, confirmación en M5, dos frames), aquí sweep y
confirmación viven en la misma serie M5: tras un sweep en la barra M5 `j`, se busca
el IFVG en las siguientes `confirm_lookback` barras M5; la entrada es la apertura de
la barra M5 posterior a la confirmación. Stop tras la mecha del sweep M5; target =
swing opuesto en M5.
"""

from __future__ import annotations

import pandas as pd

from data import schema
from strategy.liquidity_sweep_ifvg import Trade, _simulate_exit, daily_bias_from_d1
from strategy.liquidity_sweep_ifvg_v2 import _swept_pois

__all__ = ["daily_bias_from_d1", "generate_trades_v3", "trades_to_frame"]


def generate_trades_v3(
    m5: pd.DataFrame,
    daily_bias: pd.Series,
    *,
    window_start: int = 0,
    window_end: int = 4,
    confirm_lookback: int = 12,
    stop_buffer: float = 0.0,
    require_accumulation: bool = True,
) -> list[Trade]:
    """Genera operaciones con mecánica enteramente en M5 (ADR-009).

    `m5` debe traer ya calculadas (todas sobre M5): estructura (swings, sweeps,
    order blocks), acumulación (in_accumulation, acc_low/high), niveles (pdh/pdl,
    pwh/pwl, tokyo_hi/lo, equal_high/low, ob_*), IFVG (ifvg_bull/bear). El bias
    proviene de D1.

    Los POIs barridos de cada operación se guardan en `generate_trades_v3._last_pois`.
    """
    trades: list[Trade] = []
    pois: list[str] = []
    freq = pd.Timedelta(schema.freq_for("M5"))
    open_until: pd.Timestamp | None = None

    idx = m5.index
    in_window = (idx.hour >= window_start) & (idx.hour < window_end)
    positions = {ts: p for p, ts in enumerate(idx)}

    for j in idx[in_window]:
        if open_until is not None and j <= open_until:
            continue
        bias = int(daily_bias.get(j.normalize(), 0))
        if bias == 0:
            continue
        row = m5.loc[j]
        if require_accumulation and not bool(row.get("in_accumulation", False)):
            continue

        hit = _swept_pois(row, bias)
        if not hit:
            continue

        # Confirmación IFVG en las siguientes `confirm_lookback` barras M5.
        start = j + freq
        end = start + confirm_lookback * freq
        win = m5[(m5.index >= start) & (m5.index < end)]
        sig_col = "ifvg_bear" if bias == -1 else "ifvg_bull"
        conf = win.index[win[sig_col]] if sig_col in win.columns else []
        if len(conf) == 0:
            continue
        pos = positions[conf[0]]
        if pos + 1 >= len(m5):
            continue

        entry_pos = pos + 1
        entry_time = idx[entry_pos]
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
        r = (exit_price - entry_price) if side == "long" else (entry_price - exit_price)
        trades.append(Trade(
            entry_time=entry_time.isoformat(), side=side, entry_price=entry_price,
            stop=stop, target=target, exit_time=exit_time, exit_price=exit_price,
            outcome=outcome, r_multiple=(r / risk if risk > 0 else 0.0),
            cohort=str(entry_time.year),
        ))
        pois.append("+".join(hit))
        open_until = pd.Timestamp(exit_time)

    generate_trades_v3._last_pois = pois
    return trades


def trades_to_frame(trades: list[Trade], pois: list[str] | None = None) -> pd.DataFrame:
    """DataFrame de operaciones V3, con columna `poi` si se proveen los POIs."""
    from dataclasses import asdict
    df = pd.DataFrame([asdict(t) for t in trades])
    if pois is not None and len(pois) == len(trades):
        df["poi"] = pois
    return df
