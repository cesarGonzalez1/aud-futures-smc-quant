"""Confluencia diaria V13: votos del usuario codificados y calibrados (SPEC_V13 §3-5).
Candidatos elegidos por la regla fijada (mayor exactitud 3 clases en etiquetas 2024):
D1-B, H4-B, NY AM S-B, NY PM S-A.  PROVISIONAL hasta el hold-out 2026."""
from __future__ import annotations
import pandas as pd
from features import bias as bias_mod
from features.bias_user import compute_votes

CHOSEN = {"d1": "d1_B", "h4": "h4_B", "ny_am": "am_B", "ny_pm": "pm_A"}

def build_v13_confluence(m5: pd.DataFrame, h1: pd.DataFrame):
    days = sorted(pd.unique(m5.index.normalize()))
    Ts = [d + pd.Timedelta(minutes=30) for d in days if d.weekday() < 5]
    v = compute_votes(m5, h1, Ts)
    out = pd.DataFrame(index=[t.normalize() for t in Ts])
    for k, col in CHOSEN.items():
        out[k] = v[col].to_numpy()
    res = [bias_mod.combine_bias(int(r.d1), int(r.h4), int(r.ny_am), int(r.ny_pm)) for r in out.itertuples()]
    out["direction"] = [r[0] for r in res]; out["confidence"] = [r[1] for r in res]
    # candle: ayer vs hoy según D1-B (hoy = última sesión completa)
    out["dir_ayer"] = v["dir_ayer_B"].to_numpy(); out["dir_hoy"] = v["dir_hoy_B"].to_numpy()
    return out
