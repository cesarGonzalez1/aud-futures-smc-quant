"""Votos de bias del usuario codificados (SPEC_V13 §1-3). Reconstruido 2026-10-26 y validado
contra las salidas guardadas de la corrida V13 original (confluence.csv, votos_vs_etiquetas_2024.csv).

`compute_votes(m5, h1, Ts)` devuelve una fila por momento de evaluación T (en el mismo orden) con los
candidatos: d1_A, d1_B, h4_A, h4_B, am_A, am_B, pm_A, pm_B (-1/0/+1) y dir_ayer_{A,B}, dir_hoy_{A,B}.
Solo usa barras M5 con cierre <= T (point-in-time).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features import structure
from features.bias import add_structure_bias, resample_h4, session_structure_bias
from features.vwap import session_id

__all__ = ["compute_votes", "d1_vote", "sessions_table"]

M5 = pd.Timedelta("5min")
NY_AM_UTC = (12, 15)   # 6-9 am CDMX
NY_PM_UTC = (18, 21)   # 12-3 pm CDMX
SB_FRAC = 0.3          # SPEC_V13 S-B


def sessions_table(m5: pd.DataFrame) -> pd.DataFrame:
    """Sesión CME (ancla 17:00 Chicago): o,h,l,c,start,end por sesión, orden cronológico."""
    sid = session_id(m5.index)
    g = m5.groupby(sid, sort=True)
    t = pd.DataFrame({"o": g[schema.OPEN].first(), "h": g[schema.HIGH].max(),
                      "l": g[schema.LOW].min(), "c": g[schema.CLOSE].last()})
    idx = pd.Series(m5.index, index=sid)
    t["start"] = idx.groupby(level=0).first().reindex(t.index).to_numpy()
    t["end"] = idx.groupby(level=0).last().reindex(t.index).to_numpy() + M5
    return t.sort_values("start").reset_index(drop=True)


def _dir(c) -> int:
    return int(np.sign(c["c"] - c["o"]))


def d1_vote(hoy: dict, ayer: dict, p3: pd.DataFrame) -> int:
    """Regla D1 del usuario (SPEC_V13 §3). `p3` = 3 sesiones previas a `ayer` (para liquidez)."""
    dh, da = _dir(hoy), _dir(ayer)
    if da > 0 and dh > 0 and hoy["h"] > ayer["h"]:
        return 1
    if da < 0 and dh > 0 and len(p3) and ayer["l"] < p3["l"].min() and hoy["c"] > ayer["c"]:
        return 1
    if da < 0 and dh < 0 and hoy["l"] < ayer["l"]:
        return -1
    if da > 0 and dh < 0 and len(p3) and ayer["h"] > p3["h"].max() and hoy["c"] < ayer["c"]:
        return -1
    return 0


def _row(s) -> dict:
    return {"o": float(s["o"]), "h": float(s["h"]), "l": float(s["l"]), "c": float(s["c"])}


def _h4_series(h1: pd.DataFrame) -> tuple[pd.Series, pd.Series]:
    h4 = structure.add_structure(resample_h4(h1))
    a = add_structure_bias(h4)["structure_bias"]
    lsh, lsl, cl = h4["last_swing_high"].to_numpy(), h4["last_swing_low"].to_numpy(), h4[schema.CLOSE].to_numpy()
    b = np.zeros(len(h4), dtype=int)
    state = 0
    for t in range(len(h4)):                       # BOS: el estado persiste hasta la ruptura contraria
        if not np.isnan(lsh[t]) and cl[t] > lsh[t]:
            state = 1
        elif not np.isnan(lsl[t]) and cl[t] < lsl[t]:
            state = -1
        b[t] = state
    return a, pd.Series(b, index=h4.index)


def _asof(series: pd.Series, T: pd.Timestamp, lag: pd.Timedelta) -> int:
    s = series[series.index <= T - lag]
    return int(s.iloc[-1]) if len(s) else 0


def _disp(m5: pd.DataFrame, start: pd.Timestamp, end: pd.Timestamp, frac: float = SB_FRAC) -> int:
    w = m5[(m5.index >= start) & (m5.index < end)]
    if len(w) < 6:
        return 0
    rng = float(w[schema.HIGH].max() - w[schema.LOW].min())
    move = float(w[schema.CLOSE].iloc[-1] - w[schema.OPEN].iloc[0])
    return int(np.sign(move)) if rng > 0 and abs(move) >= frac * rng else 0


def compute_votes(m5: pd.DataFrame, h1: pd.DataFrame, Ts: list[pd.Timestamp]) -> pd.DataFrame:
    sess = sessions_table(m5)
    h4a, h4b = _h4_series(h1)
    am_a = session_structure_bias(m5, start_hour_utc=NY_AM_UTC[0], end_hour_utc=NY_AM_UTC[1])
    pm_a = session_structure_bias(m5, start_hour_utc=NY_PM_UTC[0], end_hour_utc=NY_PM_UTC[1])
    rows = []
    for T in Ts:
        T = pd.Timestamp(T)
        done = sess[sess["end"] <= T]
        forming = sess[(sess["start"] < T) & (sess["end"] > T)]
        r = dict(d1_A=0, d1_B=0, dir_ayer_A=0, dir_hoy_A=0, dir_ayer_B=0, dir_hoy_B=0)
        if len(done) >= 5:
            y = done.iloc[-1]
            if len(forming):                                             # A: hoy = sesión en curso hasta T
                bars = m5[(m5.index >= forming.iloc[0]["start"]) & (m5.index < T)]
                if len(bars):
                    hoy = {"o": float(bars[schema.OPEN].iloc[0]), "h": float(bars[schema.HIGH].max()),
                           "l": float(bars[schema.LOW].min()), "c": float(bars[schema.CLOSE].iloc[-1])}
                    ayer = _row(y)
                    r["d1_A"] = d1_vote(hoy, ayer, done.iloc[-4:-1])
                    r["dir_ayer_A"], r["dir_hoy_A"] = _dir(ayer), _dir(hoy)
            hoy, ayer = _row(y), _row(done.iloc[-2])                     # B: hoy = última sesión completa
            r["d1_B"] = d1_vote(hoy, ayer, done.iloc[-5:-2])
            r["dir_ayer_B"], r["dir_hoy_B"] = _dir(ayer), _dir(hoy)
        wd = T.normalize() - pd.Timedelta(days=1)                         # día UTC de las ventanas NY
        r.update(
            h4_A=_asof(h4a, T, pd.Timedelta(hours=4)), h4_B=_asof(h4b, T, pd.Timedelta(hours=4)),
            am_A=int(am_a.get(wd, 0)), am_B=_disp(m5, wd + pd.Timedelta(hours=NY_AM_UTC[0]), wd + pd.Timedelta(hours=NY_AM_UTC[1])),
            pm_A=int(pm_a.get(wd, 0)), pm_B=_disp(m5, wd + pd.Timedelta(hours=NY_PM_UTC[0]), wd + pd.Timedelta(hours=NY_PM_UTC[1])),
        )
        rows.append(r)
    return pd.DataFrame(rows)
