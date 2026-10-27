"""Hipótesis V12 — "trade de cajón" del usuario (SPEC_V12.md, fijada antes de correr).

Flujo: bias ≥3/4 (D1, H4, NY AM, NY PM) → desde 6:30 pm CDMX (00:30 UTC) sweep de
EQ/swing clasificado con VWAP → IFVG en M5 → entrada → SL en el extremo del sweep →
TP con RR 1.6-1.8 ajustado por zonas de liquidez. Máx 1 operación por día.

Cada operación se etiqueta con: bucket horario (A0/A/B/C), tipo de disparador
(eq_vwap / eq_extremo / sweep_extremo), n_alineadas, candle_aligned, profundidad del
sweep. Estos atributos NO filtran (excepto los GATE de la spec); sirven para medir
efectividad por tipo de setup.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features.liquidity_target import next_unfilled_fvg_target
from strategy.liquidity_sweep_ifvg import Trade, _simulate_exit

__all__ = ["generate_trades_v12", "time_bucket", "classify_trigger", "resolve_rr_target"]


def time_bucket(ts: pd.Timestamp) -> str:
    """Bucket por hora de ENTRADA (UTC; CDMX = UTC−6). SPEC_V12 §3."""
    m = ts.hour * 60 + ts.minute
    if 30 <= m < 60:
        return "A0"   # 6:30-7 pm
    if 60 <= m < 120:
        return "A"    # 7-8 pm
    if 120 <= m < 180:
        return "B"    # 8-9 pm
    if 180 <= m < 240:
        return "C"    # 9-10 pm
    return "fuera"


def classify_trigger(level: float, vwap_lo: float, vwap_up: float, eq_recent: bool) -> str | None:
    """SPEC_V12 §2. None = no es setup (sin EQ y nivel dentro de bandas)."""
    if any(pd.isna(x) for x in (level, vwap_lo, vwap_up)):
        return None
    inside = vwap_lo < level < vwap_up
    if eq_recent:
        return "eq_vwap" if inside else "eq_extremo"
    return None if inside else "sweep_extremo"


def resolve_rr_target(
    *, side: str, entry: float, stop: float, zones: list[tuple[str, float]],
    rr_base: float = 1.7, rr_lo: float = 1.6, rr_hi: float = 1.8,
) -> tuple[float, float, str]:
    """RR 1.7 por defecto; si la zona más cercana en dirección está a z ≤ rr_hi R,
    RR = clamp(z, rr_lo, rr_hi). Devuelve (target, rr, zona_usada)."""
    risk = abs(entry - stop)
    ahead = []
    for name, p in zones:
        if p is None or pd.isna(p):
            continue
        dist = (p - entry) if side == "long" else (entry - p)
        if dist > 0:
            ahead.append((dist / risk, name))
    rr, src = rr_base, "rr_base"
    if ahead:
        z, name = min(ahead)
        if z <= rr_hi:
            rr, src = min(rr_hi, max(rr_lo, z)), name
    target = entry + rr * risk if side == "long" else entry - rr * risk
    return float(target), float(rr), src


def generate_trades_v12(
    m5: pd.DataFrame,
    h1: pd.DataFrame,
    confluence: pd.DataFrame,
    *,
    sweep_start_minute: int = 30,     # 00:30 UTC = 6:30 pm CDMX
    window_end_hour: int = 4,         # entrada < 04:00 UTC = 10 pm CDMX
    entry_lookback: int = 12,
    min_stop_atr_frac: float = 0.3,
    fvg_lookback_bars: int = 30,
) -> pd.DataFrame:
    """Devuelve un DataFrame (una fila por operación) con Trade + atributos de setup.

    `m5` debe traer: estructura (sweeps, last_swing_*), equal_*_recent, ifvg_*, atr,
    pdh/pdl, day_hi/day_lo, vwap/vwap_up/vwap_lo, prev_dir/today_dir.
    """
    idx = m5.index
    freq = pd.Timedelta(schema.freq_for("M5"))
    positions = {ts: p for p, ts in enumerate(idx)}
    minute_of_day = idx.hour * 60 + idx.minute
    in_window = (minute_of_day >= sweep_start_minute) & (idx.hour < window_end_hour)

    rows: list[dict] = []
    open_until: pd.Timestamp | None = None
    traded_days: set = set()

    for j in idx[in_window]:
        if open_until is not None and j <= open_until:
            continue
        day = j.normalize()
        if day in traded_days or day not in confluence.index:
            continue
        crow = confluence.loc[day]
        bias = int(crow["direction"])
        if bias == 0 or str(crow["confidence"]) != "alta":      # GATE: ≥3 de 4
            continue
        votes = [int(crow[c]) for c in ("d1", "h4", "ny_am", "ny_pm")]
        n_aligned = sum(1 for v in votes if v == bias)

        row = m5.loc[j]
        side = "short" if bias == -1 else "long"
        if side == "short":
            if not bool(row.get("liquidity_sweep_high", False)):
                continue
            level, eq_recent = row.get("last_swing_high"), bool(row.get("equal_high_recent", False))
        else:
            if not bool(row.get("liquidity_sweep_low", False)):
                continue
            level, eq_recent = row.get("last_swing_low"), bool(row.get("equal_low_recent", False))

        trigger = classify_trigger(level, row.get("vwap_lo"), row.get("vwap_up"), eq_recent)
        if trigger is None:
            continue

        sig_col = "ifvg_bear" if bias == -1 else "ifvg_bull"
        win = m5[(m5.index >= j + freq) & (m5.index < j + (entry_lookback + 1) * freq)]
        hits = win.index[win[sig_col]] if sig_col in win.columns else []
        if len(hits) == 0:
            continue
        sig_t = hits[0]
        pos = positions[sig_t]
        if pos + 1 >= len(m5):
            continue
        entry_time = idx[pos + 1]
        if entry_time.normalize() != day or entry_time.hour >= window_end_hour:
            continue
        entry_price = float(m5[schema.OPEN].iloc[pos + 1])

        seg = m5.iloc[positions[j]: pos + 1]
        stop = float(seg[schema.HIGH].max()) if side == "short" else float(seg[schema.LOW].min())
        if (side == "short" and not stop > entry_price) or (side == "long" and not stop < entry_price):
            continue
        atr_j = row.get("atr")
        if pd.notna(atr_j) and abs(entry_price - stop) < min_stop_atr_frac * float(atr_j):
            continue

        sig_row = m5.loc[sig_t]
        fvg = next_unfilled_fvg_target(h1, entry_time, entry_price, side, lookback_bars=fvg_lookback_bars)
        zones = [("pdh", sig_row.get("pdh")), ("pdl", sig_row.get("pdl")),
                 ("day_hi", sig_row.get("day_hi")), ("day_lo", sig_row.get("day_lo")),
                 ("fvg_h1", fvg)]
        target, rr, zone_src = resolve_rr_target(side=side, entry=entry_price, stop=stop, zones=zones)

        exit_time, exit_price, outcome = _simulate_exit(m5, pos + 1, side, stop, target)
        risk = abs(entry_price - stop)
        r = (exit_price - entry_price) if side == "long" else (entry_price - exit_price)
        want = 1 if side == "long" else -1
        sweep_ext = float(row[schema.HIGH]) if side == "short" else float(row[schema.LOW])
        trade = Trade(
            entry_time=entry_time.isoformat(), side=side, entry_price=entry_price, stop=stop,
            target=target, exit_time=exit_time, exit_price=exit_price, outcome=outcome,
            r_multiple=(r / risk if risk > 0 else 0.0), cohort=str(entry_time.year),
        )
        d = trade.__dict__.copy()
        d.update(
            bucket=time_bucket(entry_time), trigger=trigger, n_aligned=n_aligned,
            candle_aligned=bool(int(row.get("prev_dir", 0)) == want and int(row.get("today_dir", 0)) == want),
            sweep_depth_atr=(abs(sweep_ext - float(level)) / float(atr_j)) if pd.notna(atr_j) and atr_j > 0 else np.nan,
            bars_to_ifvg=int((sig_t - j) / freq), rr=rr, zone=zone_src,
            risk_pips=risk * 1e4,
        )
        rows.append(d)
        traded_days.add(day)
        open_until = pd.Timestamp(exit_time)

    return pd.DataFrame(rows)
