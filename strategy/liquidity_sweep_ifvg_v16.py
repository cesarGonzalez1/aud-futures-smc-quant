"""V16 — codificación fiel de la descripción visual del usuario (SPEC_V16.md).

Variantes (todas definidas ANTES de medir; se elige por REPRODUCCIÓN del ledger, no por P&L):
  confirm        'ifvg'  = solo IFVG posterior al sweep (V12-V15)
                 'first' = lo que ocurra primero: IFVG o 3 velas M5 cerradas seguidas en el sentido de la operación
  sweep_lookback  antigüedad máxima (en velas M5) del último swing barrido: 50 (V12-V15) o 222 (día CDMX completo)
  trigger_gate   True = como V12 (sin EQ y nivel dentro de bandas VWAP → no se opera); False = todo sweep cuenta
  sl_tick        0.0 = SL exacto en el final del sweep; 0.00005 = 1 tick de 6A más allá
  rr_mode        'zones' = V12 (RR 1.6-1.8 por zonas); 'fixed' = RR 1.7 fijo (sin zonas)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features.liquidity_target import next_unfilled_fvg_target
from features.structure import add_structure
from strategy.liquidity_sweep_ifvg import Trade, _simulate_exit
from strategy.liquidity_sweep_ifvg_v12 import classify_trigger, resolve_rr_target, time_bucket

__all__ = ["generate_trades_v16", "with_sweep_lookback", "three_candle_signal", "TICK_6A"]

TICK_6A = 0.00005


def with_sweep_lookback(m5: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Recalcula solo las columnas de sweep con otra antigüedad máxima del swing barrido (point-in-time)."""
    if lookback == 50:
        return m5
    ohlc = m5[[schema.OPEN, schema.HIGH, schema.LOW, schema.CLOSE]]
    s = add_structure(ohlc, sweep_lookback=lookback)
    out = m5.copy()
    for c in ("liquidity_sweep_high", "liquidity_sweep_low"):
        out[c] = s[c].to_numpy()
    return out


def three_candle_signal(opens: np.ndarray, closes: np.ndarray, start: int, end: int, side: str) -> int | None:
    """Posición de la 3ª vela de la primera racha de 3 velas CERRADAS seguidas en el sentido de la operación
    (long: close>open; short: close<open), usando solo velas en [start, end]. None si no hay."""
    run = 0
    for p in range(start, end + 1):
        ok = closes[p] > opens[p] if side == "long" else closes[p] < opens[p]
        run = run + 1 if ok else 0
        if run == 3:
            return p
    return None


def generate_trades_v16(
    m5: pd.DataFrame, h1: pd.DataFrame, confluence: pd.DataFrame, *,
    confirm: str = "first", trigger_gate: bool = False, sl_tick: float = TICK_6A, rr_mode: str = "fixed",
    sweep_start_minute: int = 30, window_end_hour: int = 4, entry_lookback: int = 12,
    min_stop_atr_frac: float = 0.3, fvg_lookback_bars: int = 30, rr_fixed: float = 1.7,
) -> pd.DataFrame:
    idx = m5.index
    freq = pd.Timedelta(schema.freq_for("M5"))
    positions = {ts: p for p, ts in enumerate(idx)}
    opens, closes = m5[schema.OPEN].to_numpy(), m5[schema.CLOSE].to_numpy()
    minute_of_day = idx.hour * 60 + idx.minute
    in_window = (minute_of_day >= sweep_start_minute) & (idx.hour < window_end_hour)

    rows: list[dict] = []
    open_until = None
    traded_days: set = set()

    for j in idx[in_window]:
        if open_until is not None and j <= open_until:
            continue
        day = j.normalize()
        if day in traded_days or day not in confluence.index:
            continue
        crow = confluence.loc[day]
        bias = int(crow["direction"])
        if bias == 0 or str(crow["confidence"]) != "alta":
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
            if trigger_gate:
                continue
            trigger = "sweep_interior"

        # --- confirmación: IFVG y/o 3 velas seguidas, ambas dentro de las 12 velas M5 siguientes al sweep ---
        pj = positions[j]
        sig_col = "ifvg_bear" if bias == -1 else "ifvg_bull"
        win = m5[(m5.index >= j + freq) & (m5.index < j + (entry_lookback + 1) * freq)]
        hits = win.index[win[sig_col]] if sig_col in win.columns else []
        cand = []
        if len(hits):
            cand.append((positions[hits[0]], "ifvg"))
        if confirm == "first":
            p3 = three_candle_signal(opens, closes, pj + 1, min(pj + entry_lookback, len(idx) - 1), side)
            if p3 is not None:
                cand.append((p3, "3velas"))
        if not cand:
            continue
        pos, conf_type = min(cand)             # lo que ocurra primero; empate → IFVG
        sig_t = idx[pos]
        if pos + 1 >= len(m5):
            continue
        entry_time = idx[pos + 1]
        if entry_time.normalize() != day or entry_time.hour >= window_end_hour:
            continue
        entry_price = float(opens[pos + 1])

        seg = m5.iloc[pj: pos + 1]
        stop = float(seg[schema.HIGH].max()) + sl_tick if side == "short" else float(seg[schema.LOW].min()) - sl_tick
        if (side == "short" and not stop > entry_price) or (side == "long" and not stop < entry_price):
            continue
        atr_j = row.get("atr")
        if pd.notna(atr_j) and abs(entry_price - stop) < min_stop_atr_frac * float(atr_j):
            continue

        if rr_mode == "fixed":
            risk0 = abs(entry_price - stop)
            rr, zone_src = rr_fixed, "fijo"
            target = entry_price + rr * risk0 if side == "long" else entry_price - rr * risk0
        else:
            sig_row = m5.loc[sig_t]
            fvg = next_unfilled_fvg_target(h1, entry_time, entry_price, side, lookback_bars=fvg_lookback_bars)
            zones = [("pdh", sig_row.get("pdh")), ("pdl", sig_row.get("pdl")), ("day_hi", sig_row.get("day_hi")),
                     ("day_lo", sig_row.get("day_lo")), ("fvg_h1", fvg)]
            target, rr, zone_src = resolve_rr_target(side=side, entry=entry_price, stop=stop, zones=zones)

        exit_time, exit_price, outcome = _simulate_exit(m5, pos + 1, side, stop, target)
        risk = abs(entry_price - stop)
        r = (exit_price - entry_price) if side == "long" else (entry_price - exit_price)
        want = 1 if side == "long" else -1
        sweep_ext = float(row[schema.HIGH]) if side == "short" else float(row[schema.LOW])
        trade = Trade(entry_time=entry_time.isoformat(), side=side, entry_price=entry_price, stop=stop, target=target,
                      exit_time=exit_time, exit_price=exit_price, outcome=outcome,
                      r_multiple=(r / risk if risk > 0 else 0.0), cohort=str(entry_time.year))
        d = trade.__dict__.copy()
        d.update(
            bucket=time_bucket(entry_time), trigger=trigger, confirm_type=conf_type, n_aligned=n_aligned,
            candle_aligned=bool(int(row.get("prev_dir", 0)) == want and int(row.get("today_dir", 0)) == want),
            sweep_depth_atr=(abs(sweep_ext - float(level)) / float(atr_j)) if pd.notna(atr_j) and atr_j > 0 else np.nan,
            bars_to_confirm=int((sig_t - j) / freq), rr=rr, zone=zone_src, risk_pips=risk * 1e4,
        )
        rows.append(d)
        traded_days.add(day)
        open_until = pd.Timestamp(exit_time)
    return pd.DataFrame(rows)
