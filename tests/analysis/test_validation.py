"""Tests de validación de valor predictivo (ADR-003 enmienda: KW, epsilon², FDR, N mínimo)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.cohorts import COHORT_COL
from analysis.validation import epsilon_squared, validate_regime_predictive


def _build(regime_labels, targets, cohort="2021", rv=None):
    n = len(regime_labels)
    idx = pd.date_range("2021-01-01", periods=n, freq="1h", tz="UTC")
    df = pd.DataFrame(
        {
            "myregime": regime_labels,
            "target": targets,
            "realized_vol": rv if rv is not None else np.zeros(n),
            COHORT_COL: cohort,
        },
        index=idx,
    )
    df.index.name = "timestamp"
    return df


def test_separated_distributions_are_significant():
    rng = np.random.default_rng(0)
    a = rng.normal(0.001, 0.0001, 200)      # régimen A: vol baja
    b = rng.normal(0.010, 0.0001, 200)      # régimen B: vol alta (bien separado)
    df = _build(["A"] * 200 + ["B"] * 200, np.r_[a, b])
    res = validate_regime_predictive(df, regime_col="myregime", target_col="target")
    row = res.iloc[0]
    assert row["n_regimes"] == 2
    assert row["p_raw"] < 0.01
    assert row["epsilon2"] > 0
    assert not np.isnan(row["p_fdr"])       # FDR aplicado


def test_min_sample_drops_small_regime():
    # A y B grandes, C diminuto (< min_sample) => C descartado, quedan 2.
    labels = ["A"] * 150 + ["B"] * 150 + ["C"] * 5
    targets = np.r_[np.zeros(150), np.ones(150), np.full(5, 0.5)]
    df = _build(labels, targets)
    res = validate_regime_predictive(df, regime_col="myregime", target_col="target", min_sample=100)
    row = res.iloc[0]
    assert row["n_regimes"] == 2
    assert row["dropped_regimes"] == 1


def test_insufficient_regimes_noted():
    # Un solo régimen con N suficiente => no se puede correr KW.
    df = _build(["A"] * 120, np.zeros(120))
    res = validate_regime_predictive(df, regime_col="myregime", target_col="target")
    assert np.isnan(res.iloc[0]["p_raw"])
    assert "insuficientes" in res.iloc[0]["note"]


def test_epsilon_squared_formula():
    assert np.isnan(epsilon_squared(5.0, 2, 3))     # n<=k
    assert abs(epsilon_squared(10.0, 100, 3) - (10 - 3 + 1) / (100 - 3)) < 1e-9
