"""Tests del generador de reportes (Fase 3, sección 8)."""

from __future__ import annotations

import json

import pandas as pd

from analysis import regime as R
from data import schema
from reporting import report


def _state_df() -> pd.DataFrame:
    idx = pd.date_range("2025-06-30 20:00", periods=3, freq="1h", tz="UTC")
    df = pd.DataFrame({
        schema.CLOSE: [0.65, 0.66, 0.67],
        "adx": [10, 20, 30.0],
        "atr": [0.001, 0.001, 0.0012],
        "rsi": [40, 50, 61.0],
        "ema_trend": [0.64, 0.645, 0.65],
        R.TREND_COL: ["range", "range", "trending"],
        R.VOL_COL: ["normal", "normal", "alta"],
        R.REGIME_COL: ["range|normal", "range|normal", "trending|alta"],
        "in_london": [False, False, True],
        "in_newyork": [False, False, True],
        "liquidity_sweep_high": [False, True, False],
        "liquidity_sweep_low": [False, False, False],
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    return df


def test_current_state():
    st = report.current_state(_state_df())
    assert st["regime"] == "trending|alta"
    assert st["above_ema_trend"] is True
    assert set(st["active_sessions"]) == {"london", "newyork"}
    assert st["adx"] == 30.0


def test_recent_change_detects_transition():
    df = _state_df()
    msg = report.recent_change(df, lookback=2)
    assert "cambió" in msg and "range|normal" in msg and "trending|alta" in msg


def test_structure_summary_counts_sweeps():
    s = report.structure_summary(_state_df(), lookback=3)
    assert s["sweeps_high"] == 1
    assert s["last_sweep_high"] is not None


def test_load_walkforward_evidence(tmp_path):
    payload = {R.REGIME_COL: {"walkforward": [
        {"cohort": "2021", "p_fdr": 1e-6, "epsilon2": 0.01},
        {"cohort": "2022", "p_fdr": 0.2, "epsilon2": 0.0005},
    ]}}
    (tmp_path / "results.json").write_text(json.dumps(payload), encoding="utf-8")
    ev = report.load_walkforward_evidence(tmp_path)
    assert ev["n_cohorts"] == 2
    assert ev["n_significant"] == 1
    assert ev["epsilon2_min"] == 0.0005


def test_compose_report_has_all_sections_and_proxy_warning():
    state = {"timestamp": "2025-07-01T00:00:00+00:00", "regime": "trending|alta",
             "regime_trend": "trending", "regime_vol": "alta", "active_sessions": ["london"],
             "close": 0.67, "adx": 30.0, "atr": 0.001, "rsi": 61.0, "above_ema_trend": True}
    structure = {"lookback": 200, "sweeps_high": 2, "sweeps_low": 1,
                 "last_sweep_high": "2025-06-30T10:00:00+00:00", "last_sweep_low": None}
    evidence = {"experiment": "2026-07-01_regime_vs_garch_walkforward", "n_cohorts": 6,
                "n_significant": 6, "p_fdr_max_sig": 1e-3, "epsilon2_min": 0.002, "epsilon2_max": 0.062}
    md = report.compose_report(state, "régimen estable", structure, evidence, "2026-07-01")
    for h in ["## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6."]:
        assert h in md
    assert "proxy" in md.lower()
    assert "walk-forward" in md.lower()
    assert "No se generan señales" in md
