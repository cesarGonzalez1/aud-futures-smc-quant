"""Hipótesis de estrategia V2: Acumulación–Manipulación–Distribución (ADR-008).

Extiende V1 (`liquidity_sweep_ifvg.py`, que queda intacto y comparable). Diferencias
respecto a V1:
  - Precondición DURA de acumulación (in_accumulation, ADR-008) antes del sweep.
  - POI ampliados: además de PDH/PDL y high/low de Tokio (V1), el rango de
    acumulación, PWH/PWL, equal highs/lows y order blocks vigentes.
  - Ambas condiciones obligatorias: acumulación válida Y sweep alineado al bias.
  - Distribución idéntica a V1 (IFVG M5 → entrada barra siguiente → stop mecha →
    target swing opuesto H1).

Cada operación registra `poi` = qué tipo de nivel fue barrido, para análisis
posterior (no forma parte del cálculo del backtest).

Reutiliza de V1: bias diario, simulación de salida, dataclass de resultado.
"""

from __future__ import annotations

import pandas as pd

from data import schema
from strategy.liquidity_sweep_ifvg import Trade, _simulate_exit, daily_bias_from_d1

__all__ = ["daily_bias_from_d1", "generate_trades_v2", "trades_to_frame"]


def _swept_pois(row, bias: int) -> list[str]:
    """POIs (ADR-008) barridos por la barra H1 en dirección del bias. Lista de nombres."""
    hit: list[str] = []
    if bias == -1:  # sweep de máximos: high > nivel y close < nivel
        candidates = {
            "pdh": row.get("pdh"), "pwh": row.get("pwh"),
            "tokyo_hi": row.get("tokyo_hi"), "acc_high": row.get("acc_high"),
            "equal_high": row.get("last_swing_high") if row.get("equal_high") else None,
            "ob_bear": row.get("ob_bear_low"),  # OB bajista como resistencia
        }
        for name, lvl in candidates.items():
            if pd.notna(lvl) and row[schema.HIGH] > lvl and row[schema.CLOSE] < lvl:
                hit.append(name)
    elif bias == 1:  # sweep de mínimos: low < nivel y close > nivel
        candidates = {
            "pdl": row.get("pdl"), "pwl": row.get("pwl"),
            "tokyo_lo": row.get("tokyo_lo"), "acc_low": row.get("acc_low"),
            "equal_low": row.get("last_swing_low") if row.get("equal_low") else None,
            "ob_bull": row.get("ob_bull_high"),  # OB alcista como soporte
        }
        for name, lvl in candidates.items():
            if pd.notna(lvl) and row[schema.LOW] < lvl and row[schema.CLOSE] > lvl:
                hit.append(name)
    return hit


def generate_trades_v2(
    h1: pd.DataFrame,
    m5: pd.DataFrame,
    daily_bias: pd.Series,
    *,
    window_start: int = 0,
    window_end: int = 4,
    confirm_lookback_m5: int = 12,
    stop_buffer: float = 0.0,
    require_accumulation: bool = True,
) -> list[Trade]:
    """Genera operaciones según ADR-008 (AMD).

    Requiere en `h1` (además de lo de V1): in_accumulation, acc_low/high, pwh/pwl,
    equal_high/low, ob_*_low/high. En `m5`: ifvg_bull/bear.

    `poi` de cada Trade se guarda como sufijo del campo `side` no — se añade como
    columna aparte vía trades_to_frame (el dataclass Trade no la tiene, así que se
    adjunta en un dict paralelo). Para mantener el dataclass compartido con V1, el
    POI se codifica en el atributo `outcome`? No: se devuelve en una lista paralela.
    """
    trades: list[Trade] = []
    pois: list[str] = []
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

        # Precondición dura de acumulación (ADR-008).
        if require_accumulation and not bool(row.get("in_accumulation", False)):
            continue

        hit = _swept_pois(row, bias)
        if not hit:
            continue

        start = j + freq_h1
        end = start + confirm_lookback_m5 * freq_m5
        win = m5[(m5.index >= start) & (m5.index < end)]
        sig_col = "ifvg_bear" if bias == -1 else "ifvg_bull"
        conf = win.index[win[sig_col]] if sig_col in win.columns else []
        if len(conf) == 0:
            continue
        pos = m5.index.get_loc(conf[0])
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
        r = (exit_price - entry_price) if side == "long" else (entry_price - exit_price)
        trades.append(Trade(
            entry_time=entry_time.isoformat(), side=side, entry_price=entry_price,
            stop=stop, target=target, exit_time=exit_time, exit_price=exit_price,
            outcome=outcome, r_multiple=(r / risk if risk > 0 else 0.0),
            cohort=str(entry_time.year),
        ))
        pois.append("+".join(hit))
        open_until = pd.Timestamp(exit_time)

    generate_trades_v2._last_pois = pois  # POIs de la última corrida (análisis posterior)
    return trades


def trades_to_frame(trades: list[Trade], pois: list[str] | None = None) -> pd.DataFrame:
    """DataFrame de operaciones V2, con columna `poi` si se proveen los POIs."""
    from dataclasses import asdict
    df = pd.DataFrame([asdict(t) for t in trades])
    if pois is not None and len(pois) == len(trades):
        df["poi"] = pois
    return df
