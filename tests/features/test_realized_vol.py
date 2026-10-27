"""Tests de volatilidad realizada y del target forward (secciones 2, 7.2)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features import realized_vol


def _frame(n: int = 30) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    rng = np.random.default_rng(3)
    close = 100 + np.cumsum(rng.normal(0, 0.5, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0, 0.3, n)
    low = np.minimum(open_, close) - rng.uniform(0, 0.3, n)
    df = pd.DataFrame(
        {schema.OPEN: open_, schema.HIGH: high, schema.LOW: low, schema.CLOSE: close},
        index=idx,
    )
    df.index.name = schema.TIMESTAMP
    return df


def test_realized_vol_is_backward_and_nonnegative():
    df = _frame()
    out = realized_vol.add_realized_vol(df, window=6)
    rv = out["realized_vol"]
    assert rv.iloc[:5].isna().all()      # warmup sin suficientes barras
    assert (rv.dropna() >= 0).all()


def test_forward_target_matches_manual_sum():
    df = _frame()
    horizon = 4
    out = realized_vol.add_forward_vol_target(df, horizon=horizon)
    col = f"target_fwd_vol_{horizon}"

    # Cálculo manual del GK por barra para verificar la ventana forward.
    o, h, l, c = df[schema.OPEN], df[schema.HIGH], df[schema.LOW], df[schema.CLOSE]
    gk = (0.5 * np.log(h / l) ** 2 - (2 * np.log(2) - 1) * np.log(c / o) ** 2).clip(lower=0)

    t = 10
    expected = np.sqrt(gk.iloc[t + 1 : t + 1 + horizon].sum())
    assert np.isclose(out[col].iloc[t], expected)

    # Las últimas `horizon` barras no tienen futuro suficiente -> NaN.
    assert out[col].iloc[-horizon:].isna().all()
