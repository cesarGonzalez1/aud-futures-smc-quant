"""Puerta V15 (SPEC_V15): >=2 de {d1,h4,ny_am} a favor y NINGUNO en contra. NY PM = información."""
from __future__ import annotations
import numpy as np
import pandas as pd
from strategy.v13_confluence import build_v13_confluence


def gate_v15(conf: pd.DataFrame) -> pd.DataFrame:
    out = conf.copy()
    v = out[["d1", "h4", "ny_am"]].to_numpy()
    bull, bear = (v == 1).sum(1), (v == -1).sum(1)
    open_bull, open_bear = (bull >= 2) & (bear == 0), (bear >= 2) & (bull == 0)
    out["direction"] = np.where(open_bull, 1, np.where(open_bear, -1, 0)).astype(int)
    out["confidence"] = np.where(out["direction"] != 0, "alta", "na")
    out["gate_tipo"] = np.where(~(open_bull | open_bear), "cerrada", np.where((bull == 3) | (bear == 3), "tres", "dos_neutral"))
    return out


def build_v15_confluence(m5: pd.DataFrame, h1: pd.DataFrame) -> pd.DataFrame:
    return gate_v15(build_v13_confluence(m5, h1))
