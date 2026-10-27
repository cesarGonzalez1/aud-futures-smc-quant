"""Hipótesis única V4: señal/entrada de V3 (M5) + stop en el swing H1 (ADR-010).

Extiende V3 (`liquidity_sweep_ifvg_v3.py`, intacto y comparable). ÚNICO cambio: el
stop deja de ser la mecha del sweep M5 y pasa a ser el **swing H1** del lado
barrido, mapeado point-in-time a cada barra M5 (columnas `h1_swing_high` /
`h1_swing_low`, provistas por el backtest vía merge_asof backward). Motivado por el
diagnóstico de V3 (stops M5 tan ajustados que los costos, fijos en precio, dominan
al normalizar por R). NO es una búsqueda de anchos: es esta única redefinición.

Señal, POI, confirmación IFVG, entrada y target = idénticos a V3.
"""

from __future__ import annotations

import pandas as pd

from data import schema
from strategy.liquidity_sweep_ifvg import Trade, _simulate_exit, daily_bias_from_d1
from strategy.liquidity_sweep_ifvg_v2 import _swept_pois

__all__ = ["daily_bias_from_d1", "generate_trades_v4", "trades_to_frame"]


def generate_trades_v4(
    m5: pd.DataFrame,
    daily_bias: pd.Series,
    *,
    window_start: int = 0,
    window_end: int = 4,
    confirm_lookback: int = 12,
    stop_buffer: float = 0.0,
    require_accumulation: bool = True,
) -> list[Trade]:
    """Igual que V3 pero el stop usa el swing H1 vigente (ADR-010).

    `m5` debe traer, además de todo lo de V3, las columnas `h1_swing_high` y
    `h1_swing_low` (último swing H1 confirmado ≤ t, point-in-time).
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

        # --- ÚNICO cambio vs V3: stop = swing H1 del lado barrido ---
        if side == "short":
            stop = row.get("h1_swing_high")
            target = row.get("last_swing_low")
            if pd.isna(stop) or not (stop > entry_price):
                continue
            if pd.isna(target) or not (target < entry_price):
                continue
            stop = float(stop) + stop_buffer
        else:
            stop = row.get("h1_swing_low")
            target = row.get("last_swing_high")
            if pd.isna(stop) or not (stop < entry_price):
                continue
            if pd.isna(target) or not (target > entry_price):
                continue
            stop = float(stop) - stop_buffer
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

    generate_trades_v4._last_pois = pois
    return trades


def trades_to_frame(trades: list[Trade], pois: list[str] | None = None) -> pd.DataFrame:
    """DataFrame de operaciones V4, con columna `poi` si se proveen los POIs."""
    from dataclasses import asdict
    df = pd.DataFrame([asdict(t) for t in trades])
    if pois is not None and len(pois) == len(trades):
        df["poi"] = pois
    return df
