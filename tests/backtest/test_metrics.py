"""Tests de costos y métricas (Fase 4, sección 6.3)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from backtest import metrics


def _trades(r_multiples, cohort="2021"):
    n = len(r_multiples)
    return pd.DataFrame({
        "entry_price": [1.0] * n,
        "stop": [0.99] * n,          # riesgo = 0.01
        "r_multiple": r_multiples,
        "cohort": [cohort] * n,
    })


def test_apply_costs_reduces_r():
    t = _trades([2.0, -1.0])
    out = metrics.apply_costs(t, half_spread=0.0005, slippage_atr_frac=0.0, atr=0.0)
    # costo precio = 2*0.0005 = 0.001; riesgo 0.01 => cost_r = 0.1
    assert np.allclose(out["cost_r"], 0.1)
    assert np.allclose(out["r_net"], [1.9, -1.1])


def test_compute_metrics_basic():
    t = _trades([2.0, -1.0, -1.0, 2.0])
    t["r_net"] = t["r_multiple"]
    m = metrics.compute_metrics(t)
    assert m["n_trades"] == 4
    assert m["win_rate"] == 0.5
    assert np.isclose(m["expectancy"], 0.5)
    assert np.isclose(m["r_total"], 2.0)


def test_max_drawdown():
    # R = [1,1,-1,-1,-1,1] -> equity [1,2,1,0,-1,0] -> pico 2, mínimo -1 => DD=3
    t = _trades([1, 1, -1, -1, -1, 1])
    t["r_net"] = t["r_multiple"]
    m = metrics.compute_metrics(t)
    assert np.isclose(m["max_drawdown_r"], 3.0)


def test_metrics_by_cohort_has_all_row():
    t = pd.concat([_trades([1.0, -1.0], "2021"), _trades([2.0], "2022")], ignore_index=True)
    t["r_net"] = t["r_multiple"]
    res = metrics.metrics_by_cohort(t)
    assert set(res["cohort"]) == {"2021", "2022", "ALL"}
    assert int(res[res["cohort"] == "ALL"]["n_trades"].iloc[0]) == 3


def test_empty_trades_safe():
    m = metrics.compute_metrics(pd.DataFrame())
    assert m["n_trades"] == 0
