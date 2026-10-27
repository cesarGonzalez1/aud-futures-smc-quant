"""Dirección de la vela diaria previa y de la vela de HOY en curso (V12, SPEC_V12.md §1).

Día de trading anclado a las 17:00 America/Chicago (apertura CME), igual que
`features.vwap.session_id`.

- `today_dir[t]`  = signo(close[t] − open de la sesión): lo que se "ve" hoy hasta t.
- `prev_dir[t]`   = signo(close final − open) de la sesión ANTERIOR completa.
  La sesión anterior terminó antes de que empiece la actual → point-in-time.

Valores: +1 alcista, −1 bajista, 0 neutral/sin dato.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features.vwap import session_id

__all__ = ["add_trading_day_candle"]


def add_trading_day_candle(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    sid = session_id(out.index)
    g_open = out[schema.OPEN].groupby(sid).transform("first")
    out["today_dir"] = np.sign(out[schema.CLOSE] - g_open).astype(int)

    sess = pd.DataFrame({
        "o": out[schema.OPEN].groupby(sid).first(),
        "c": out[schema.CLOSE].groupby(sid).last(),
    }).sort_index()
    prev_dir = np.sign(sess["c"] - sess["o"]).shift(1).fillna(0).astype(int)
    out["prev_dir"] = pd.Series(sid, index=out.index).map(prev_dir).fillna(0).astype(int).to_numpy()
    return out
