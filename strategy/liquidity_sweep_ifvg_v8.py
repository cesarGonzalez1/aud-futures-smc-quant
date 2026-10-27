"""Hipótesis V8 (ADR-015) — igual que V7, cambia SOLO el stop: swing M5 en vez
de swing H1.

Diagnóstico de V7 (`experiments/..._v7/report.md`): el win rate ya es el más
alto de las 7 versiones (52.8%), pero `avg_win` (0.67R) < `avg_loss` (1.13R) —
el problema es reward:risk, no tasa de acierto. V7b (target más lejos) lo
empeoró (bajó el win rate más de lo que subió el tamaño de ganancia). Esta
hipótesis ataca el OTRO lado de la razón R: reducir el riesgo (stop) en vez de
aumentar la recompensa (target).

`features.structure.add_structure`, cuando se aplica sobre M5 (como ya hace
`_prepare` en V4-V7), calcula `last_swing_high`/`last_swing_low` a escala M5
(point-in-time, más ajustado). Ese swing M5 ya existe en el pipeline — V1-V7
nunca lo usaron para el stop, solo lo usaron como fallback de target
(`swing_opposite`/BOS en `resolve_target`/`resolve_target_v7`). El swing H1
mapeado (`h1_swing_high`/`h1_swing_low`, ADR-010) es el que se ha usado como
stop desde V4.

V8 usa el swing M5 DEL LADO BARRIDO (mismo swing que originó el sweep en la
capa 1) como stop, en vez del swing H1. Todo lo demás — confirmación MSS/CISD,
zona de entrada IFVG, jerarquía de target (incluida Quarter Theory) — es
IDÉNTICO a V7, para aislar el efecto de este único cambio.

Riesgo esperado: un stop más ajustado sube la razón R por operación ganadora,
pero también puede aumentar la probabilidad de ser barrido por ruido antes de
que el precio vaya en la dirección esperada (menor win rate). Se reporta el
resultado real, no se asume de antemano cuál efecto domina.
"""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd

from data import schema
from features.liquidity_target import resolve_target_v7
from features.mss_cisd import find_cisd
from features.quarter_theory import add_quarter_context
from strategy.liquidity_sweep_ifvg import Trade, _simulate_exit
from strategy.liquidity_sweep_ifvg_v5 import _equal_poi_swept
from strategy.liquidity_sweep_ifvg_v7 import _find_confirmation

__all__ = ["generate_trades_v8", "trades_to_frame"]


def generate_trades_v8(
    m5: pd.DataFrame,
    h1: pd.DataFrame,
    confluence: pd.DataFrame,
    *,
    window_start: int = 0,
    window_end: int = 4,
    confirmation_lookback: int = 12,
    entry_lookback: int = 12,
    stop_buffer: float = 0.0,
    fvg_lookback_bars: int = 30,
    quarter_step: float = 0.0025,
    quarter_n_levels: int = 1,
    min_stop_atr_frac: float = 0.3,
    confirmation_require: str = "any",
) -> tuple[list[Trade], list[str], list[str], list[str], list[bool]]:
    """Idéntico a `generate_trades_v7` salvo el stop: swing M5 (`last_swing_high`/
    `last_swing_low`, de la barra del sweep `j`) en vez de swing H1
    (`h1_swing_high`/`h1_swing_low`). Ver docstring del módulo.

    `min_stop_atr_frac`: filtro de realismo de ejecución, NO un ajuste post-resultado
    (sección 6.2) — un swing M5 puede quedar a una distancia mínima (unos pocos
    ticks) del precio de entrada; ese stop no es operable en la realidad (el
    spread/slippage por sí solos lo consumirían, y el tamaño de posición implícito
    para arriesgar un monto fijo sería impracticable). Se descarta cualquier
    operación cuyo riesgo (`|entry-stop|`) sea menor a `min_stop_atr_frac` × ATR de
    la barra del sweep. Si no hay columna `atr`, no se aplica el filtro.
    """
    m5 = add_quarter_context(m5, step=quarter_step)

    trades: list[Trade] = []
    confidences: list[str] = []
    target_sources: list[str] = []
    confirmation_sources: list[str] = []
    quarter_aligned: list[bool] = []

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
        # --- Capa 1: disparador primario (igual que V5/V7). ---
        if not _equal_poi_swept(row, bias):
            continue

        # --- Capa 2: confirmación MSS o CISD (igual que V7). ---
        confirm_t, confirm_src = _find_confirmation(
            m5, j, bias, lookback_bars=confirmation_lookback, require=confirmation_require,
        )
        if confirm_t is None:
            continue

        # --- Capa 4: zona de entrada FVG/IFVG (igual que V7). ---
        start = confirm_t + freq
        end = start + entry_lookback * freq
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

        # --- Stop: ÚNICO cambio frente a V7 — swing M5 (de la barra del sweep `j`),
        # no swing H1. ---
        if side == "short":
            stop = row.get("last_swing_high")
            if pd.isna(stop) or not (float(stop) > entry_price):
                continue
            stop = float(stop) + stop_buffer
        else:
            stop = row.get("last_swing_low")
            if pd.isna(stop) or not (float(stop) < entry_price):
                continue
            stop = float(stop) - stop_buffer

        atr_j = row.get("atr")
        if pd.notna(atr_j) and abs(entry_price - stop) < min_stop_atr_frac * float(atr_j):
            continue

        # --- Capa 5: objetivo (igual que V7). ---
        target, target_source = resolve_target_v7(
            h1_fvg=h1, m5_row=m5.loc[entry_time], entry_time=entry_time, entry_price=entry_price,
            side=side, lookback_bars=fvg_lookback_bars, quarter_step=quarter_step,
            quarter_n_levels=quarter_n_levels,
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
        confirmation_sources.append(confirm_src)
        quarter_aligned.append(bool(m5.loc[entry_time, "near_quarter_level"]))
        open_until = pd.Timestamp(exit_time)

    return trades, confidences, target_sources, confirmation_sources, quarter_aligned


def trades_to_frame(
    trades: list[Trade],
    confidences: list[str] | None = None,
    target_sources: list[str] | None = None,
    confirmation_sources: list[str] | None = None,
    quarter_aligned: list[bool] | None = None,
) -> pd.DataFrame:
    df = pd.DataFrame([asdict(t) for t in trades])
    for name, values in (
        ("confidence", confidences),
        ("target_source", target_sources),
        ("confirmation_source", confirmation_sources),
        ("quarter_aligned", quarter_aligned),
    ):
        if values is not None and len(values) == len(trades):
            df[name] = values
    return df
