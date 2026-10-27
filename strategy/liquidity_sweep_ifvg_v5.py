"""Hipótesis V5: bias de confluencia multi-timeframe + equal highs/lows + salida
jerárquica "próximo punto de liquidez" (ADR-011).

Extiende V4 (`liquidity_sweep_ifvg_v4.py`, intacto y comparable). Diferencias:

  - **Bias**: en vez del régimen D1 (ADR-007), usa la confluencia de 4 fuentes de
    bias por ESTRUCTURA de swings (D1, H4, sesión NY AM, sesión NY PM —
    `features/bias.py`). 3+ alineadas => operar (confianza 'alta'). 2 alineadas +
    2 neutrales => operar con cautela (confianza 'baja', se guarda como columna
    `confidence` en cada operación, no excluye la entrada). Cualquier otro caso =>
    no operar ese día.
  - **POI**: únicamente equal highs/lows (`equal_high_recent`/`equal_low_recent`,
    ADR-011) formados desde 22:00 UTC del día anterior — no el conjunto ampliado
    de V2 (order blocks, PDH/PDL, etc.). Es una regla más angosta y deliberada.
  - **Confirmación IFVG**: idéntica a V3/V4 (M5).
  - **Entrada**: idéntica a V3/V4 (apertura de la barra M5 siguiente a la
    confirmación).
  - **Stop**: por default, igual que V4 (swing H1 del lado barrido, mapeado
    point-in-time). Esto es una decisión heredada de V4, NO especificada
    explícitamente por el usuario para V5 — queda documentada aquí como supuesto
    a confirmar/ajustar, no como hecho consumado.
  - **Target**: jerarquía de `features.liquidity_target.resolve_target` (FVG H1 sin
    rellenar > extremo del día si viene oscilando > swing opuesto M5), en vez del
    swing opuesto fijo de V1-V4.

Cada operación registra `confidence` (alta/baja) y `target_source`
(fvg_h1/day_range/swing_opposite) para análisis posterior — no afectan el cálculo,
son informativas.
"""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from data import schema
from features.liquidity_target import resolve_target
from strategy.liquidity_sweep_ifvg import Trade, _simulate_exit

__all__ = ["generate_trades_v5", "trades_to_frame"]


def _equal_poi_swept(row, bias: int) -> bool:
    """¿Hubo sweep de un equal high/low "reciente" (formado desde 22:00 UTC del
    día anterior) en la dirección del bias? (ADR-011, único tipo de POI en V5).
    """
    if bias == -1:
        return bool(row.get("equal_high_recent", False)) and bool(row.get("liquidity_sweep_high", False))
    if bias == 1:
        return bool(row.get("equal_low_recent", False)) and bool(row.get("liquidity_sweep_low", False))
    return False


def generate_trades_v5(
    m5: pd.DataFrame,
    h1: pd.DataFrame,
    confluence: pd.DataFrame,
    *,
    window_start: int = 0,
    window_end: int = 4,
    confirm_lookback: int = 12,
    stop_buffer: float = 0.0,
    fvg_lookback_bars: int = 30,
) -> tuple[list[Trade], list[str], list[str]]:
    """Genera operaciones según ADR-011.

    Args:
        m5: M5 con toda la mecánica ya calculada (estructura, equal_high_recent/
            equal_low_recent, ifvg_bull/bear, regime_vol, day_hi/day_lo,
            h1_swing_high/h1_swing_low ya mapeados point-in-time, igual que V4).
        h1: H1 con columnas de FVG (`features.fvg.detect_fvg`) para la prioridad 1
            de la jerarquía de salida.
        confluence: salida de `features.bias.build_daily_confluence`, indexada por
            día de trading (columnas `direction`, `confidence`).

    Returns:
        (trades, confidences, target_sources) — listas paralelas a `trades`.
    """
    trades: list[Trade] = []
    confidences: list[str] = []
    target_sources: list[str] = []
    freq = pd.Timedelta(schema.freq_for("M5"))
    open_until: pd.Timestamp | None = None

    idx = m5.index
    in_window = (idx.hour >= window_start) & (idx.hour < window_end)
    positions = {ts: p for p, ts in enumerate(idx)}

    for j in idx[in_window]:
        if open_until is not None and j <= open_until:
            continue  # una posición a la vez

        day = j.normalize()
        if day not in confluence.index:
            continue
        bias = int(confluence.loc[day, "direction"])
        confidence = str(confluence.loc[day, "confidence"])
        if bias == 0:
            continue

        row = m5.loc[j]
        if not _equal_poi_swept(row, bias):
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

        # --- Stop: igual que V4 (swing H1 del lado barrido). Supuesto heredado,
        # no especificado explícitamente para V5 — ver docstring del módulo. ---
        if side == "short":
            stop = row.get("h1_swing_high")
            if pd.isna(stop) or not (float(stop) > entry_price):
                continue
            stop = float(stop) + stop_buffer
        else:
            stop = row.get("h1_swing_low")
            if pd.isna(stop) or not (float(stop) < entry_price):
                continue
            stop = float(stop) - stop_buffer

        # --- Target: jerarquía "próximo punto de liquidez" (ADR-011). ---
        target, target_source = resolve_target(
            h1_fvg=h1, m5_row=row, entry_time=entry_time, entry_price=entry_price,
            side=side, lookback_bars=fvg_lookback_bars,
        )
        if target is None:
            continue

        exit_time, exit_price, outcome = _simulate_exit(m5, entry_pos, side, stop, target)
        risk = abs(entry_price - stop)
        r = (exit_price - entry_price) if side == "long" else (entry_price - exit_price)
        trades.append(Trade(
            entry_time=entry_time.isoformat(), side=side, entry_price=entry_price,
            stop=stop, target=target, exit_time=exit_time, exit_price=exit_price,
            outcome=outcome, r_multiple=(r / risk if risk > 0 else 0.0),
            cohort=str(entry_time.year),
        ))
        confidences.append(confidence)
        target_sources.append(target_source)
        open_until = pd.Timestamp(exit_time)

    return trades, confidences, target_sources


def trades_to_frame(
    trades: list[Trade],
    confidences: list[str] | None = None,
    target_sources: list[str] | None = None,
) -> pd.DataFrame:
    """DataFrame de operaciones V5, con columnas `confidence`/`target_source` si
    se proveen (informativas, no afectan el cálculo de métricas)."""
    df = pd.DataFrame([asdict(t) for t in trades])
    if confidences is not None and len(confidences) == len(trades):
        df["confidence"] = confidences
    if target_sources is not None and len(target_sources) == len(trades):
        df["target_source"] = target_sources
    return df
