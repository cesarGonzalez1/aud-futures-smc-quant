"""Tests del baseline GARCH(1,1) y de la validación sobre su residual."""

from __future__ import annotations

import numpy as np
import pandas as pd

from analysis.cohorts import COHORT_COL
from analysis import garch_baseline as G
from data import schema


def _price_series(n: int, seed: int = 0) -> pd.Series:
    idx = pd.date_range("2021-01-01", periods=n, freq="1h", tz="UTC")
    rng = np.random.default_rng(seed)
    close = 0.68 + np.cumsum(rng.normal(0, 0.0008, n))
    s = pd.Series(close, index=idx, name=schema.CLOSE)
    s.index.name = "timestamp"
    return s


def test_garch_forecast_is_finite_and_positive():
    close = _price_series(400)
    fc = G.garch_forecast_vol(close, horizon=6)
    valid = fc.dropna()
    assert len(valid) > 300
    assert (valid > 0).all()


def test_garch_forecast_too_short_returns_nan():
    close = _price_series(20)
    fc = G.garch_forecast_vol(close, horizon=6)
    assert fc.isna().all()


def test_walkforward_finite_positive():
    close = _price_series(2000)
    fc = G.garch_forecast_vol_walkforward(close, horizon=6, refit_every=200, min_train=500)
    assert fc.iloc[:400].isna().all()          # antes de min_train no hay pronóstico
    valid = fc.dropna()
    assert len(valid) > 1000
    assert (valid > 0).all()


def test_walkforward_is_point_in_time():
    # El pronóstico en t no cambia al truncar la serie después de t: mismos refits
    # (deterministas) y solo datos <= t. index 1200 cae en el segmento [1100,1300).
    close = _price_series(2000, seed=5)
    full = G.garch_forecast_vol_walkforward(close, 6, refit_every=200, min_train=500)
    trunc = G.garch_forecast_vol_walkforward(close.iloc[:1500], 6, refit_every=200, min_train=500)
    assert np.isclose(full.iloc[1200], trunc.iloc[1200], rtol=1e-9, equal_nan=True)


def test_walkforward_short_returns_nan():
    close = _price_series(100)
    fc = G.garch_forecast_vol_walkforward(close, 6, min_train=1000)
    assert fc.isna().all()


def test_regime_shift_survives_on_residual():
    # Régimen B con target mucho mayor que cualquier pronóstico GARCH => el residual
    # difiere fuerte por régimen => KW significativo sobre el residual.
    n = 400
    close = _price_series(n, seed=1)
    df = pd.DataFrame(index=close.index)
    df[schema.CLOSE] = close
    df[COHORT_COL] = "2021"
    df["myregime"] = ["A"] * (n // 2) + ["B"] * (n // 2)
    rng = np.random.default_rng(2)
    target = np.r_[rng.normal(0.001, 0.0001, n // 2), rng.normal(0.05, 0.0001, n // 2)]
    df["target"] = target

    res = G.validate_regime_over_garch_residual(
        df, regime_col="myregime", target_col="target", horizon=6, min_sample=50
    )
    row = res.iloc[0]
    assert row["n_regimes"] == 2
    assert row["p_raw"] < 0.05          # el régimen sí separa el residual
    assert not np.isnan(row["p_fdr"])
    assert np.isfinite(row["garch_rmse"])
