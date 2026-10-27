from __future__ import annotations

from datetime import datetime

import pandas as pd
import pytest

from data.sources.tradingview_csv import TradingViewCSVSource


def _write_csv(path, rows, time_col="time"):
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)


def test_fetch_reads_iso_time_csv(tmp_path):
    _write_csv(tmp_path / "6A_H1.csv", {
        "time": ["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z", "2024-01-01T02:00:00Z"],
        "open": [0.65, 0.66, 0.67], "high": [0.66, 0.67, 0.68],
        "low": [0.64, 0.65, 0.66], "close": [0.655, 0.665, 0.675],
        "Volume": [100, 200, 150],
    })
    src = TradingViewCSVSource(import_dir=str(tmp_path))
    out = src.fetch("6A", "H1", datetime(2024, 1, 1), datetime(2024, 1, 2))
    assert len(out) == 3
    assert list(out["close"]) == [0.655, 0.665, 0.675]
    assert out.index.tz is not None


def test_fetch_reads_unix_time_csv(tmp_path):
    _write_csv(tmp_path / "6A_D1.csv", {
        "time": [1704067200, 1704153600],  # 2024-01-01, 2024-01-02 UTC
        "open": [0.65, 0.66], "high": [0.66, 0.67], "low": [0.64, 0.65], "close": [0.655, 0.665],
    })
    src = TradingViewCSVSource(import_dir=str(tmp_path))
    out = src.fetch("6A", "D1", datetime(2024, 1, 1), datetime(2024, 1, 3))
    assert len(out) == 2


def test_fetch_concatenates_multiple_chunk_files(tmp_path):
    _write_csv(tmp_path / "6A_M5.csv", {
        "time": ["2024-01-01T00:00:00Z", "2024-01-01T00:05:00Z"],
        "open": [0.65, 0.66], "high": [0.66, 0.67], "low": [0.64, 0.65], "close": [0.655, 0.665],
    })
    _write_csv(tmp_path / "6A_M5__2.csv", {
        "time": ["2024-01-01T00:05:00Z", "2024-01-01T00:10:00Z"],  # una vela se solapa a propósito
        "open": [0.66, 0.67], "high": [0.67, 0.68], "low": [0.65, 0.66], "close": [0.665, 0.675],
    })
    src = TradingViewCSVSource(import_dir=str(tmp_path))
    out = src.fetch("6A", "M5", datetime(2024, 1, 1), datetime(2024, 1, 2))
    assert len(out) == 3  # 4 filas, 1 duplicada por timestamp -> 3 únicas


def test_fetch_raises_clear_error_when_no_files(tmp_path):
    src = TradingViewCSVSource(import_dir=str(tmp_path))
    with pytest.raises(FileNotFoundError, match="Exporta desde TradingView"):
        src.fetch("6A", "M1", datetime(2024, 1, 1), datetime(2024, 1, 2))


def test_fetch_raises_clear_error_on_missing_ohlc_columns(tmp_path):
    _write_csv(tmp_path / "6A_H4.csv", {"time": ["2024-01-01T00:00:00Z"], "close": [0.65]})
    src = TradingViewCSVSource(import_dir=str(tmp_path))
    with pytest.raises(ValueError, match="OHLC"):
        src.fetch("6A", "H4", datetime(2024, 1, 1), datetime(2024, 1, 2))


def test_fetch_filters_to_requested_range(tmp_path):
    _write_csv(tmp_path / "6A_D1.csv", {
        "time": ["2023-01-01T00:00:00Z", "2024-06-01T00:00:00Z", "2025-01-01T00:00:00Z"],
        "open": [0.6, 0.65, 0.7], "high": [0.61, 0.66, 0.71], "low": [0.59, 0.64, 0.69],
        "close": [0.605, 0.655, 0.705],
    })
    src = TradingViewCSVSource(import_dir=str(tmp_path))
    out = src.fetch("6A", "D1", datetime(2024, 1, 1), datetime(2024, 12, 31))
    assert len(out) == 1
    assert out.index[0].year == 2024
