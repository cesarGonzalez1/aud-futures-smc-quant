"""Fixtures compartidas: datasets sintéticos con respuesta conocida (sección 13).

Los tests de calidad usan datos de juguete donde el resultado correcto se conoce
de antemano, no datos reales de mercado.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from data import schema


def _ohlcv_frame(index: pd.DatetimeIndex, close: np.ndarray) -> pd.DataFrame:
    """Construye un OHLCV canónico coherente a partir de una serie de cierres."""
    close = np.asarray(close, dtype=float)
    open_ = np.empty_like(close)
    open_[0] = close[0]
    open_[1:] = close[:-1]
    high = np.maximum(open_, close) + 0.0005
    low = np.minimum(open_, close) - 0.0005
    df = pd.DataFrame(
        {
            schema.OPEN: open_,
            schema.HIGH: high,
            schema.LOW: low,
            schema.CLOSE: close,
            schema.VOLUME: np.full_like(close, 100.0),
        },
        index=index,
    )
    df.index.name = schema.TIMESTAMP
    return df


@pytest.fixture
def clean_h1() -> pd.DataFrame:
    """Dataset H1 limpio de 48 barras horarias continuas en UTC."""
    idx = pd.date_range("2023-01-02 00:00", periods=48, freq="1h", tz="UTC")
    rng = np.random.default_rng(42)
    close = 0.68 + np.cumsum(rng.normal(0, 0.0003, size=48))
    return _ohlcv_frame(idx, close)
