"""Test anti-look-ahead de features (sección 6.1).

Principio: un feature point-in-time calculado en `t` no debe cambiar si se
recalcula sobre la serie recortada hasta `t`. Se recalcula el pipeline completo
sobre `df[:t+1]` y se compara la fila `t` contra el cálculo sobre la serie entera.

El TARGET (`target_fwd_vol_*`) se EXCLUYE porque usa futuro por diseño (es el label,
no un feature) — de hecho, si NO se excluyera, este test debería fallar sobre él,
lo que confirma que el target está correctamente marcado como forward-looking.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features import indicators, realized_vol, sessions, structure

SESSIONS_CFG = {
    "London": {"tz": "Europe/London", "open_local": "08:00", "close_local": "17:00"},
    "NewYork": {"tz": "America/New_York", "open_local": "08:00", "close_local": "17:00"},
}


def _synthetic(n: int = 220) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
    rng = np.random.default_rng(7)
    close = 0.68 + np.cumsum(rng.normal(0, 0.0008, n))
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0, 0.001, n)
    low = np.minimum(open_, close) - rng.uniform(0, 0.001, n)
    df = pd.DataFrame(
        {schema.OPEN: open_, schema.HIGH: high, schema.LOW: low, schema.CLOSE: close,
         schema.VOLUME: 100.0},
        index=idx,
    )
    df.index.name = schema.TIMESTAMP
    return df


def _pipeline(df: pd.DataFrame) -> pd.DataFrame:
    out = indicators.add_trend_momentum(df)
    out = indicators.add_volatility(out)
    out = sessions.add_sessions(out, SESSIONS_CFG)
    out = structure.add_structure(out)
    out = realized_vol.add_realized_vol(out)
    out = realized_vol.add_forward_vol_target(out)  # target: se excluirá al comparar
    return out


def test_features_are_point_in_time():
    df = _synthetic()
    full = _pipeline(df)

    feature_cols = [c for c in full.columns if not c.startswith("target_")]
    feature_cols = [c for c in feature_cols if c not in schema.OHLCV_COLUMNS]

    for t in (150, 180, 205):
        truncated = _pipeline(df.iloc[: t + 1])
        a = full.iloc[t][feature_cols]
        b = truncated.iloc[t][feature_cols]
        for col in feature_cols:
            va, vb = a[col], b[col]
            if isinstance(va, (bool, np.bool_)):
                assert va == vb, f"{col} en t={t} cambió (look-ahead)"
            else:
                assert np.isclose(float(va), float(vb), equal_nan=True), (
                    f"{col} en t={t}: full={va} vs truncado={vb} (look-ahead)"
                )


def test_target_uses_future_by_design():
    # Confirmación de que el target SÍ depende del futuro (no es point-in-time):
    # al truncar, el valor del target en t cerca del borde cambia respecto al full.
    df = _synthetic()
    full = _pipeline(df)
    t = 200
    truncated = _pipeline(df.iloc[: t + 1])  # sin futuro tras t
    col = "target_fwd_vol_6"
    # En el full hay futuro (t+1..t+6); en el truncado no -> NaN o distinto.
    assert not np.isclose(
        float(full.iloc[t][col]), float(truncated.iloc[t][col]), equal_nan=True
    )
