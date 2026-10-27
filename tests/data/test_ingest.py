"""Tests de `data.ingest.ingest_one` — en particular el manejo de 0 filas
(ADR-018: Yahoo intradía puede devolver un DataFrame vacío legítimamente,
sin que eso sea un fallo de calidad ni deba intentar escribirse)."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from data import schema
from data.ingest import ingest_one
from data.sources.base import DataSource


class _EmptySource(DataSource):
    name = "fake_empty"

    def fetch(self, symbol, timeframe, start, end):
        idx = pd.DatetimeIndex([], tz="UTC", name=schema.TIMESTAMP)
        return pd.DataFrame({c: pd.Series(dtype="float64") for c in
                              [schema.OPEN, schema.HIGH, schema.LOW, schema.CLOSE, schema.VOLUME]}, index=idx)


class _NonEmptySource(DataSource):
    name = "fake_nonempty"

    def fetch(self, symbol, timeframe, start, end):
        idx = pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC", name=schema.TIMESTAMP)
        return pd.DataFrame({
            schema.OPEN: [1.0] * 5, schema.HIGH: [1.01] * 5, schema.LOW: [0.99] * 5,
            schema.CLOSE: [1.0] * 5, schema.VOLUME: [10.0] * 5,
        }, index=idx)


def test_ingest_one_empty_dataframe_is_ok_not_a_quality_failure(tmp_path):
    result = ingest_one(
        _EmptySource(), "6A", "M1", datetime(2020, 1, 1), datetime(2025, 1, 1),
        raw_base=str(tmp_path), download_ts=datetime.now(timezone.utc).isoformat(),
        quality_cfg={}, role=schema.ROLE_REAL,
    )
    assert result.ok is True
    assert result.rows == 0
    assert "no es un error" in result.message
    assert "FALLÓ" not in result.message
    # no debe haber escrito ningún archivo
    assert list(tmp_path.rglob("*.parquet")) == []


def test_ingest_one_nonempty_dataframe_still_writes(tmp_path):
    result = ingest_one(
        _NonEmptySource(), "6A", "H1", datetime(2024, 1, 1), datetime(2024, 1, 2),
        raw_base=str(tmp_path), download_ts=datetime.now(timezone.utc).isoformat(),
        quality_cfg={}, role=schema.ROLE_REAL,
    )
    assert result.ok is True
    assert result.rows == 5
    assert list(tmp_path.rglob("*.parquet")) != []
