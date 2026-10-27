"""Tests de bias por estructura de mercado, multi-timeframe (ADR-011)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features import bias, structure


def _ohlc(idx, values, spread=0.005) -> pd.DataFrame:
    df = pd.DataFrame({
        schema.OPEN: values, schema.HIGH: [v + spread for v in values],
        schema.LOW: [v - spread for v in values], schema.CLOSE: values,
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    return df


def test_structure_bias_neutral_before_two_swings():
    # Muy pocas barras: no debe alcanzar a confirmar 2 swings de cada lado.
    idx = pd.date_range("2024-01-01", periods=6, freq="1h", tz="UTC")
    df = _ohlc(idx, [1.0, 1.01, 1.02, 1.01, 1.0, 0.99])
    s = structure.add_structure(df, k=2)
    s = bias.add_structure_bias(s)
    assert (s["structure_bias"] == 0).all()


def test_bias_known_before_day_never_uses_current_day():
    b = pd.Series([1, 1, -1, -1], index=pd.to_datetime(
        ["2024-01-01 05:00", "2024-01-02 10:00", "2024-01-03 05:00", "2024-01-03 20:00"], utc=True))
    out = bias.bias_known_before_day(b)
    assert out.loc[pd.Timestamp("2024-01-01", tz="UTC")] == 0
    assert out.loc[pd.Timestamp("2024-01-02", tz="UTC")] == 1
    # El día 2024-01-03 NO debe ver el -1 de las 05:00 de ese MISMO día (dato futuro
    # respecto a las 00:00 UTC de ese día) — debe seguir viendo el 1 del día anterior.
    assert out.loc[pd.Timestamp("2024-01-03", tz="UTC")] == 1


def test_resample_h4_aggregates_ohlc_correctly():
    idx = pd.date_range("2024-01-01 00:00", periods=8, freq="1h", tz="UTC")
    h1 = pd.DataFrame({
        schema.OPEN: [1.0, 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7],
        schema.HIGH: [1.05, 1.15, 1.25, 1.35, 1.45, 1.55, 1.65, 1.75],
        schema.LOW: [0.95, 1.05, 1.15, 1.25, 1.35, 1.45, 1.55, 1.65],
        schema.CLOSE: [1.02, 1.12, 1.22, 1.32, 1.42, 1.52, 1.62, 1.72],
    }, index=idx)
    h1.index.name = schema.TIMESTAMP
    h4 = bias.resample_h4(h1)
    assert len(h4) == 2
    assert h4[schema.OPEN].iloc[0] == 1.0
    assert h4[schema.CLOSE].iloc[0] == 1.32
    assert h4[schema.HIGH].iloc[0] == 1.35
    assert h4[schema.LOW].iloc[0] == 0.95


def test_combine_bias_confluence_rules():
    assert bias.combine_bias(1, 1, 1, 0) == (1, "alta")
    assert bias.combine_bias(1, 1, 0, 0) == (1, "baja")
    assert bias.combine_bias(1, 1, -1, 0) == (0, "na")   # 2 alineados + 1 opuesto -> no operar
    assert bias.combine_bias(1, -1, 1, -1) == (0, "na")  # 2 vs 2
    assert bias.combine_bias(0, 0, 0, 0) == (0, "na")
    assert bias.combine_bias(-1, -1, -1, 1) == (-1, "alta")
    assert bias.combine_bias(-1, -1, 0, 0) == (-1, "baja")


def test_session_structure_bias_isolated_per_window():
    # No debe lanzar error con ventanas cortas (menos de 2k+1 barras) -> bias 0.
    idx = pd.date_range("2024-03-01 00:00", periods=20, freq="5min", tz="UTC")
    df = _ohlc(idx, np.linspace(1.0, 1.01, 20), spread=0.001)
    s = bias.session_structure_bias(df, start_hour_utc=12, end_hour_utc=15)
    assert isinstance(s, pd.Series)
