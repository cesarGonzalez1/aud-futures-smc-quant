"""Hipótesis V7 — jerarquía discrecional completa del usuario (ADR-015).

Codifica, por primera vez de punta a punta, la jerarquía real de 5 capas que
el usuario usa para operar en vivo (no una simplificación de investigación):

    1. Disparadores primarios: EQL/EQH + Liquidity Sweep       (igual que V5)
    2. Confirmaciones:        MSS, CISD, (SMT — pendiente, ver nota)  <- NUEVO
    3. Contexto:              Demand Zones, Fibonacci, Quarter Theory <- NUEVO (informativo)
    4. Zona de entrada:       FVG / IFVG                        (igual que V1-V6)
    5. Objetivo:              BOS, Quarter levels                <- NUEVO (`resolve_target_v7`)

Extiende V5 (`liquidity_sweep_ifvg_v5.py`, intacto y comparable): reutiliza su
confluencia de bias (`features.bias`) y su POI de equal highs/lows sin cambio.
La diferencia real de V7 está en la CAPA 2 (nueva: exige MSS o CISD, no solo la
IFVG, antes de buscar la zona de entrada) y en la CAPA 5 (`resolve_target_v7`,
que añade Quarter Theory entre FVG-H1 y el rango del día).

**Nota SMT (pendiente, ADR-016 propuesto):** SMT es divergencia 6A vs 6N. Este
proyecto solo tiene datos de AUD/USD (proxy) — no hay 6N ingerido todavía (ADR-006
solo trajo 6A D1 como activo real, no 6N). Sin datos de 6N, SMT no puede
calcularse ni backtestearse: se documenta como brecha, no se aproxima ni se
inventa. V7 opera con 2 de las 3 confirmaciones (MSS, CISD); SMT se añadirá
cuando exista ingesta de 6N (requiere ADR nuevo, sección 16: "no agregar
activos... sin que el usuario lo pida explícitamente" — ya lo pidió vía la
jerarquía completa, pendiente solo la implementación de la fuente de datos).

**Contexto (capa 3) es INFORMATIVO, no gate:** Demand Zones ya están cubiertas
por el POI de equal highs/lows heredado de V5 (no se reimplementan); Fibonacci
50-61.8% y Quarter Theory se calculan y registran por operación
(`near_quarter_level`) pero NO excluyen entradas — la lección de V2-V5 (sección
6.2) es que sobre-filtrar por confluencias adicionales reduce el tamaño de
muestra sin evidencia previa de que mejoren el resultado; se registran para
poder analizarlas post-hoc, igual que `confidence`/`target_source` en V5.
Fibonacci 50-61.8% específicamente queda pendiente de un origen de swing pair
point-in-time bien definido — se deja como columna futura, no se aproxima aquí.

**Stop:** heredado de V5/V4 (swing H1 del lado barrido) — mismo supuesto no
especificado explícitamente por el usuario para esta versión, documentado igual
que en V5, para aislar el efecto de las capas 2 y 5 (que sí son nuevas) sin
mezclar además un cambio de stop.
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

__all__ = ["generate_trades_v7", "trades_to_frame"]


def _find_confirmation(
    m5: pd.DataFrame,
    sweep_time: pd.Timestamp,
    bias: int,
    *,
    lookback_bars: int,
    require: str = "any",
) -> tuple[pd.Timestamp | None, str]:
    """Busca MSS o CISD dentro de `lookback_bars` velas M5 tras `sweep_time`.

    Devuelve (timestamp de confirmación, fuente) — fuente en {"mss", "cisd",
    "none"}. Si ambas ocurren, se usa la que ocurre PRIMERO en el tiempo (no hay
    prioridad fija entre ellas, a diferencia de la jerarquía de capas, porque
    ambas son la misma capa 2 — confirmaciones alternativas, no en orden).

    `require`: "any" (default, igual V7), "mss" o "cisd" — restringe la búsqueda
    a una sola fuente. Necesario para probar cada confirmación de forma
    independiente y justa (una muestra generada exigiendo SOLO una fuente no es
    lo mismo que filtrar post-hoc las operaciones donde esa fuente ganó la
    carrera contra la otra — con `require` la otra fuente ni siquiera compite
    por el mismo timestamp de confirmación).
    """
    freq = pd.Timedelta(schema.freq_for("M5"))
    start = sweep_time + freq
    end = start + lookback_bars * freq
    window = m5[(m5.index >= start) & (m5.index < end)]
    if window.empty:
        return None, "none"

    direction = "bear" if bias == -1 else "bull"
    mss_col = "mss_bear" if bias == -1 else "mss_bull"

    mss_t = None
    if require in ("any", "mss"):
        mss_hit = window.index[window[mss_col]] if mss_col in window.columns else []
        mss_t = mss_hit[0] if len(mss_hit) else None

    cisd_t = None
    if require in ("any", "cisd"):
        reference_open = float(m5.loc[sweep_time, schema.OPEN])
        cisd_t = find_cisd(window, reference_open, direction)

    candidates = [(t, src) for t, src in ((mss_t, "mss"), (cisd_t, "cisd")) if t is not None]
    if not candidates:
        return None, "none"
    candidates.sort(key=lambda x: x[0])
    return candidates[0]


def generate_trades_v7(
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
    confirmation_require: str = "any",
) -> tuple[list[Trade], list[str], list[str], list[str], list[bool]]:
    """Genera operaciones según la jerarquía discrecional completa (ADR-015).

    Args:
        m5: M5 con toda la mecánica de V5 (estructura, equal_high/low_recent,
            ifvg_bull/bear, regime_vol, day_hi/day_lo, h1_swing_high/low,
            ATR) MÁS `mss_bull`/`mss_bear` (`features.mss_cisd.add_mss_flags`).
        h1: H1 con columnas de FVG (igual que V5), para la capa 5.
        confluence: salida de `features.bias.build_daily_confluence` (igual V5).
        confirmation_lookback: velas M5 tras el sweep para buscar MSS/CISD (capa 2).
        entry_lookback: velas M5 tras la confirmación para buscar IFVG (capa 4).

    Returns:
        (trades, confidences, target_sources, confirmation_sources, quarter_aligned)
        — listas paralelas a `trades`.
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
        # --- Capa 1: disparador primario (igual que V5). ---
        if not _equal_poi_swept(row, bias):
            continue

        # --- Capa 2: confirmación MSS o CISD (NUEVO en V7). ---
        confirm_t, confirm_src = _find_confirmation(
            m5, j, bias, lookback_bars=confirmation_lookback, require=confirmation_require,
        )
        if confirm_t is None:
            continue

        # --- Capa 4: zona de entrada FVG/IFVG, buscada DESPUÉS de la confirmación. ---
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

        # --- Stop: heredado de V5/V4 (swing H1 del lado barrido). ---
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

        # --- Capa 5: objetivo (BOS / Quarter Theory / FVG-H1 / rango del día). ---
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
