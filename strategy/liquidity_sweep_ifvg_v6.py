"""Hipótesis V6 (ADR-014): señal simple de V1 (ADR-007) + stop de swing H1
(ADR-010) + gestión de trailing por estructura (ADR-013, aplicada después en el
backtest, no aquí).

Motivación: de las 9 variantes probadas (V1-V5, +breakeven, +trailing), V1 —la
más simple, sin confluencia ni AMD— tuvo la mejor expectativa (−0.27R). El stop
de V1 es la mecha del propio sweep en H1 (ya relativamente ancho comparado con
V3, que usa M5), pero no es el swing estructural H1 real — es solo el extremo de
la vela que hizo el sweep. V6 prueba: misma señal de entrada de V1, pero stop =
el swing H1 confirmado (más ancho aún, mismo criterio que ADR-010 aplicó sobre
V3), para luego combinarlo con el trailing de ADR-013 en el backtest.

Todo lo demás es IDÉNTICO a V1: bias D1, sweep H1 sobre PDH/PDL/Tokio, IFVG M5,
entrada en la apertura siguiente, target = swing H1 opuesto. Reutiliza
directamente `daily_bias_from_d1`, `_sweep_at` y `_simulate_exit` de
`strategy.liquidity_sweep_ifvg` — no se reimplementa nada de eso.
"""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from data import schema
from strategy.liquidity_sweep_ifvg import Trade, _simulate_exit, _sweep_at

__all__ = ["generate_trades_v6", "trades_to_frame"]


def generate_trades_v6(
    h1: pd.DataFrame,
    m5: pd.DataFrame,
    daily_bias: pd.Series,
    *,
    window_start: int = 0,
    window_end: int = 4,
    confirm_lookback_m5: int = 12,
    stop_buffer: float = 0.0,
) -> list[Trade]:
    """Genera operaciones: señal de V1 (ADR-007), stop de swing H1 (ADR-010).

    Requiere que `h1` traiga `last_swing_high`/`last_swing_low`
    (`features.structure.add_structure`) además de las columnas ya usadas por V1
    (pdh, pdl, tokyo_hi, tokyo_lo).
    """
    trades: list[Trade] = []
    freq_m5 = pd.Timedelta(schema.freq_for("M5"))
    freq_h1 = pd.Timedelta(schema.freq_for("H1"))
    open_until: pd.Timestamp | None = None

    in_window = (h1.index.hour >= window_start) & (h1.index.hour < window_end)
    for j in h1.index[in_window]:
        if open_until is not None and j <= open_until:
            continue
        bias = int(daily_bias.get(j.normalize(), 0))
        if bias == 0:
            continue
        row = h1.loc[j]
        if not _sweep_at(row, bias):
            continue

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

        # --- Único cambio respecto a V1: stop = swing H1 confirmado, no la mecha
        # de la vela del sweep (ADR-010 aplicado a la señal de V1). ---
        if side == "short":
            stop = row.get("last_swing_high")
            if pd.isna(stop) or not (float(stop) > entry_price):
                continue
            stop = float(stop) + stop_buffer
            target = row.get("last_swing_low")
            if pd.isna(target) or not (float(target) < entry_price):
                continue
        else:
            stop = row.get("last_swing_low")
            if pd.isna(stop) or not (float(stop) < entry_price):
                continue
            stop = float(stop) - stop_buffer
            target = row.get("last_swing_high")
            if pd.isna(target) or not (float(target) > entry_price):
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
        open_until = pd.Timestamp(exit_time)

    return trades


def trades_to_frame(trades: list[Trade]) -> pd.DataFrame:
    return pd.DataFrame([asdict(t) for t in trades])
