import numpy as np
import pandas as pd

from analysis.validate_proxy import _align, _swing_alignment
from data import schema


def _h1(n: int, seed: int, tz_start: str = "2024-01-01") -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range(tz_start, periods=n, freq="1h", tz="UTC")
    close = 1.0 + np.cumsum(rng.normal(0, 0.001, n))
    high = close + np.abs(rng.normal(0, 0.0005, n))
    low = close - np.abs(rng.normal(0, 0.0005, n))
    df = pd.DataFrame({
        schema.OPEN: close, schema.HIGH: high, schema.LOW: low, schema.CLOSE: close,
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    return df


def test_align_keeps_only_overlapping_timestamps():
    real = _h1(10, seed=1)
    proxy = _h1(15, seed=1, tz_start="2024-01-01 00:00")  # se solapa completo con real (mismo inicio)
    out = _align(real, proxy)
    assert len(out) == 10  # el solape es el tamaño del mas chico
    assert set(out.columns) == {"real_close", "real_high", "real_low", "proxy_close", "proxy_high", "proxy_low"}


def test_align_empty_when_no_overlap():
    real = _h1(5, seed=1, tz_start="2020-01-01")
    proxy = _h1(5, seed=1, tz_start="2024-01-01")
    out = _align(real, proxy)
    assert out.empty


def test_swing_alignment_perfect_match_when_series_identical():
    df = _h1(60, seed=7)
    result = _swing_alignment(df, df.copy())
    # la misma serie comparada consigo misma -> todos los swings deben matchear
    if result["swing_high_n"] > 0:
        assert result["swing_high_match_rate"] == 1.0
    if result["swing_low_n"] > 0:
        assert result["swing_low_match_rate"] == 1.0


def test_swing_alignment_handles_no_swings_gracefully():
    idx = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC")
    flat = pd.DataFrame({
        schema.OPEN: [1.0] * 5, schema.HIGH: [1.0] * 5, schema.LOW: [1.0] * 5, schema.CLOSE: [1.0] * 5,
    }, index=idx)
    flat.index.name = schema.TIMESTAMP
    result = _swing_alignment(flat, flat.copy())
    assert result["swing_high_n"] == 0
    assert np.isnan(result["swing_high_match_rate"])
