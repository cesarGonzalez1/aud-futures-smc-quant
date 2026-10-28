"""Puerta V14 (SPEC_V14): D1-B, H4-B y NY AM S-B los tres alineados. NY PM = información, no puerta."""
from __future__ import annotations
import pandas as pd
from strategy.v13_confluence import build_v13_confluence


def gate_v14(conf: pd.DataFrame) -> pd.DataFrame:
    """direction=±1/'alta' solo si d1, h4 y ny_am son no neutrales e iguales; si no 0/'na'. Conserva ny_pm."""
    out = conf.copy()
    same = (out["d1"] != 0) & (out["d1"] == out["h4"]) & (out["d1"] == out["ny_am"])
    out["direction"] = out["d1"].where(same, 0).astype(int)
    out["confidence"] = same.map({True: "alta", False: "na"})
    return out


def build_v14_confluence(m5: pd.DataFrame, h1: pd.DataFrame) -> pd.DataFrame:
    return gate_v14(build_v13_confluence(m5, h1))
