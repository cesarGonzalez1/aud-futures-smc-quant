"""Gestión de operación post-entrada: breakeven móvil (ADR-012, regla real del
usuario, no una convención de la industria).

Se aplica como capa POSTERIOR a la generación de operaciones de cualquier versión
(V1-V5): NO cambia entrada, stop inicial ni target — solo RE-SIMULA la salida con
una regla dinámica: el stop se mueve a breakeven (precio de entrada, con un
colchón opcional de costo) la primera vez que el precio se mueve a favor al menos
`breakeven_trigger_r` veces el riesgo inicial (default 0.4R, punto medio de "el
primer swing/nivel cercano a favor, ~0.3-0.5R" — aproximación explícita, no una
detección estructural del swing real, documentada como tal).

Sin salidas parciales: regla explícita del usuario — posición completa, sale en
el target (jerárquico o swing opuesto, según la versión base) o en el stop
(original o ya movido a breakeven).

Aproximación intrabarra: igual convención que
`strategy.liquidity_sweep_ifvg._simulate_exit` (ya evalúa stop antes que target
dentro de la misma barra). Aquí, dentro de cada barra se evalúa primero si el
movimiento favorable disparó el breakeven (usando el extremo de esa barra), y
LUEGO se evalúa stop/target con el stop ya actualizado si aplica. Es una
aproximación de secuencia intrabarra, no un dato tick a tick — misma limitación
que el resto del backtest, declarada explícitamente.
"""

from __future__ import annotations

from dataclasses import replace

import pandas as pd

from data import schema
from strategy.liquidity_sweep_ifvg import Trade

DEFAULT_BREAKEVEN_TRIGGER_R = 0.4  # punto medio de 0.3-0.5R (regla real del usuario)


def _simulate_exit_breakeven(
    m5: pd.DataFrame,
    entry_pos: int,
    side: str,
    initial_stop: float,
    target: float,
    entry_price: float,
    *,
    breakeven_trigger_r: float,
    cost_buffer: float = 0.0,
):
    """Simula la salida barra a barra con breakeven móvil, desde `entry_pos`.

    Returns:
        (exit_time_iso, exit_price, outcome) con outcome en
        {"target", "breakeven", "stop", "open"}. "breakeven" es un caso especial
        de salida por stop, pero se distingue para poder analizar cuántas
        operaciones se "rescataron" del stop completo.
    """
    h = m5[schema.HIGH].to_numpy()
    l = m5[schema.LOW].to_numpy()
    idx = m5.index
    risk = abs(entry_price - initial_stop)
    stop = initial_stop
    triggered = False

    for p in range(entry_pos, len(m5)):
        if not triggered and risk > 0:
            favorable = (h[p] - entry_price) if side == "long" else (entry_price - l[p])
            if favorable / risk >= breakeven_trigger_r:
                triggered = True
                stop = (entry_price + cost_buffer) if side == "long" else (entry_price - cost_buffer)

        if side == "short":
            if h[p] >= stop:
                return idx[p].isoformat(), stop, ("breakeven" if triggered else "stop")
            if l[p] <= target:
                return idx[p].isoformat(), target, "target"
        else:
            if l[p] <= stop:
                return idx[p].isoformat(), stop, ("breakeven" if triggered else "stop")
            if h[p] >= target:
                return idx[p].isoformat(), target, "target"

    return idx[-1].isoformat(), float(m5[schema.CLOSE].iloc[-1]), "open"


def apply_breakeven_management(
    trades: list[Trade],
    m5: pd.DataFrame,
    *,
    breakeven_trigger_r: float = DEFAULT_BREAKEVEN_TRIGGER_R,
    cost_buffer: float = 0.0,
) -> list[Trade]:
    """Re-simula la salida de cada operación con breakeven móvil (ADR-012).

    Entrada, stop INICIAL y target no cambian (se conservan tal cual de la
    versión base). Solo se recalculan `exit_time`, `exit_price`, `outcome` y
    `r_multiple` (normalizado siempre por el riesgo INICIAL, misma convención
    que el resto del proyecto — no por el riesgo ya reducido tras el breakeven).

    NOTA (ADR-013): esta función se conserva porque su resultado (negativo,
    documentado) es conocimiento real — un breakeven al precio EXACTO de entrada,
    sin colchón, resultó ser PEOR que no gestionar nada (ver CLAUDE.md, sección de
    Fase 4). La regla real del usuario resultó ser un trailing por estructura
    (`apply_structure_trailing_stop`, abajo), no este breakeven simple. Se deja
    disponible para comparación, no como recomendación.
    """
    out: list[Trade] = []
    for t in trades:
        entry_pos = m5.index.get_loc(pd.Timestamp(t.entry_time))
        if isinstance(entry_pos, slice):
            entry_pos = entry_pos.start
        exit_time, exit_price, outcome = _simulate_exit_breakeven(
            m5, entry_pos, t.side, t.stop, t.target, t.entry_price,
            breakeven_trigger_r=breakeven_trigger_r, cost_buffer=cost_buffer,
        )
        risk = abs(t.entry_price - t.stop)
        r = (exit_price - t.entry_price) if t.side == "long" else (t.entry_price - exit_price)
        out.append(replace(
            t, exit_time=exit_time, exit_price=exit_price, outcome=outcome,
            r_multiple=(r / risk if risk > 0 else 0.0),
        ))
    return out


# ============================================================================
# ADR-013 — Trailing stop por ESTRUCTURA (la regla real del usuario)
# ============================================================================
#
# El usuario NO mueve el stop a precio de entrada. Mueve el stop al swing
# confirmado que queda "un impulso atrás" del más reciente — nunca al más
# nuevo (deja colchón para el retroceso normal), y el stop solo se mueve a
# favor (nunca se afloja). Ejemplo dado: con 2 impulsos formados, usa el
# primero; con 3, usa el segundo — siempre el penúltimo confirmado.
#
# Para un SHORT, los "impulsos" relevantes son los swing HIGHS que se forman en
# cada retroceso (el stop debe quedar arriba del precio). Para un LONG, son los
# swing LOWS. Reutiliza exactamente la misma detección de swings de ADR-004
# (`features/structure.py`, columnas `swing_high_confirmed`/`swing_low_confirmed`/
# `last_swing_high`/`last_swing_low`) — misma confirmación con lag point-in-time,
# nada nuevo del lado de la estructura, solo la lógica de cuál usar como stop.


def _simulate_exit_trailing_structure(
    m5: pd.DataFrame,
    entry_pos: int,
    side: str,
    initial_stop: float,
    target: float,
    *,
    lag_swings: int = 1,
):
    """Simula la salida con trailing stop por estructura (ADR-013).

    `lag_swings=1` = siempre usa el penúltimo swing confirmado desde la entrada
    (deja 1 impulso de colchón), igual que la regla descrita por el usuario.

    Returns:
        (exit_time_iso, exit_price, outcome) con outcome en
        {"target", "trailing_stop", "stop", "open"}. "trailing_stop" distingue
        una salida donde el stop ya se había movido, de "stop" (nunca se movió).
    """
    h = m5[schema.HIGH].to_numpy()
    l = m5[schema.LOW].to_numpy()
    idx = m5.index

    if side == "short":
        conf = m5["swing_high_confirmed"].to_numpy()
        price_col = m5["last_swing_high"].to_numpy()
    else:
        conf = m5["swing_low_confirmed"].to_numpy()
        price_col = m5["last_swing_low"].to_numpy()

    stop = initial_stop
    moved = False
    swings_seen: list[float] = []

    for p in range(entry_pos, len(m5)):
        if conf[p] and not pd.isna(price_col[p]):
            swings_seen.append(float(price_col[p]))
            if len(swings_seen) > lag_swings + 1:
                swings_seen.pop(0)
            if len(swings_seen) >= lag_swings + 1:
                candidate = swings_seen[-(lag_swings + 1)]
                # Solo ratchet a favor: nunca afloja el stop.
                if side == "short" and candidate < stop:
                    stop = candidate
                    moved = True
                elif side == "long" and candidate > stop:
                    stop = candidate
                    moved = True

        if side == "short":
            if h[p] >= stop:
                return idx[p].isoformat(), stop, ("trailing_stop" if moved else "stop")
            if l[p] <= target:
                return idx[p].isoformat(), target, "target"
        else:
            if l[p] <= stop:
                return idx[p].isoformat(), stop, ("trailing_stop" if moved else "stop")
            if h[p] >= target:
                return idx[p].isoformat(), target, "target"

    return idx[-1].isoformat(), float(m5[schema.CLOSE].iloc[-1]), "open"


def apply_structure_trailing_stop(
    trades: list[Trade],
    m5: pd.DataFrame,
    *,
    lag_swings: int = 1,
) -> list[Trade]:
    """Re-simula la salida de cada operación con trailing stop por estructura
    (ADR-013, la regla real del usuario). Entrada, stop INICIAL y target no
    cambian — solo `exit_time`/`exit_price`/`outcome`/`r_multiple` (normalizado
    por el riesgo INICIAL, misma convención que el resto del proyecto).
    """
    out: list[Trade] = []
    for t in trades:
        entry_pos = m5.index.get_loc(pd.Timestamp(t.entry_time))
        if isinstance(entry_pos, slice):
            entry_pos = entry_pos.start
        exit_time, exit_price, outcome = _simulate_exit_trailing_structure(
            m5, entry_pos, t.side, t.stop, t.target, lag_swings=lag_swings,
        )
        risk = abs(t.entry_price - t.stop)
        r = (exit_price - t.entry_price) if t.side == "long" else (t.entry_price - exit_price)
        out.append(replace(
            t, exit_time=exit_time, exit_price=exit_price, outcome=outcome,
            r_multiple=(r / risk if risk > 0 else 0.0),
        ))
    return out
