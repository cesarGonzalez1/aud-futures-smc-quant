"""Tests del adaptador Yahoo futures (6A) y validación con calendario CME (ADR-006).

No golpean la red: prueban la normalización pura (`_normalize`) sobre una salida
sintética con el mismo formato que `yf.download`, y la validación de calidad con
el calendario CME_FX sobre series diarias construidas a mano.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from data import schema
from data.sources.yahoo_futures import YahooFuturesSource
from data.validation import quality


def _yf_like_frame() -> pd.DataFrame:
    """Replica el formato de yf.download para un solo ticker (columnas MultiIndex)."""
    dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
    dates.name = "Date"
    prices = ["Adj Close", "Close", "High", "Low", "Open", "Volume"]
    cols = pd.MultiIndex.from_product([prices, ["6A=F"]], names=["Price", "Ticker"])
    data = {
        ("Adj Close", "6A=F"): [0.676, 0.673, 0.675],
        ("Close", "6A=F"): [0.676, 0.673, 0.675],
        ("High", "6A=F"): [0.684, 0.677, 0.678],
        ("Low", "6A=F"): [0.676, 0.670, 0.672],
        ("Open", "6A=F"): [0.681, 0.676, 0.673],
        ("Volume", "6A=F"): [113, 240, 180],
    }
    return pd.DataFrame(data, index=dates, columns=cols)


def test_normalize_to_canonical_schema():
    out = YahooFuturesSource._normalize(_yf_like_frame())
    assert list(out.columns) == list(schema.OHLCV_COLUMNS)
    assert out.index.name == schema.TIMESTAMP
    assert str(out.index.tz) == "UTC"
    assert out.index[0] == pd.Timestamp("2024-01-02 00:00:00+00:00")
    assert out.index.is_monotonic_increasing


def test_fetch_rejects_unknown_symbol_and_timeframe():
    src = YahooFuturesSource()
    import pytest
    with pytest.raises(ValueError):
        src.fetch("AUDUSD", "D1", None, None)   # no mapeado en Yahoo futures
    with pytest.raises(ValueError):
        src.fetch("6A", "M15", None, None)       # M15 no soportado (ADR-018: M1/M5/H1/H4/D1)


def _daily_6a(dates: list[str]) -> pd.DataFrame:
    idx = pd.DatetimeIndex(pd.to_datetime(dates), name=schema.TIMESTAMP).tz_localize("UTC")
    n = len(dates)
    close = np.linspace(0.66, 0.68, n)
    df = pd.DataFrame(
        {schema.OPEN: close, schema.HIGH: close + 0.002,
         schema.LOW: close - 0.002, schema.CLOSE: close, schema.VOLUME: 100.0},
        index=idx,
    )
    return df


def test_cme_holiday_gap_is_warning_not_error():
    # Salto sobre el feriado del 4-jul + fin de semana. Con calendario CME_FX, todos
    # los huecos deben ser WARNING (nunca error): el fin de semana como esperado y el
    # feriado clasificado vía calendario. (CME_FX puede considerar el 4-jul operable
    # con sesión recortada; en ese caso se reporta como día faltante, igual warning.)
    dates = ["2024-07-01", "2024-07-02", "2024-07-03", "2024-07-05", "2024-07-08", "2024-07-09"]
    df = _daily_6a(dates)
    report = quality.validate(df, "D1", market_calendar="CME_FX")
    assert report.is_valid                      # ningún error
    assert any("CME_FX" in w for w in report.warnings)     # clasificado vía calendario
    assert any("fin de semana" in w for w in report.warnings)


def test_cme_missing_trading_day_flagged_as_warning():
    # Falta el 2024-07-02 (martes, día hábil CME) -> hueco NO explicado por feriado.
    dates = ["2024-07-01", "2024-07-03", "2024-07-05"]
    df = _daily_6a(dates)
    report = quality.validate(df, "D1", market_calendar="CME_FX")
    assert report.is_valid                      # sigue siendo warning, no error
    assert any("faltantes" in w for w in report.warnings)


def test_cme_frame_detects_duplicates_and_order():
    df = _daily_6a(["2024-07-01", "2024-07-02", "2024-07-03"])
    dup = pd.concat([df, df.iloc[[0]]]).sort_index()
    assert any("duplicad" in e for e in quality.check_index(dup).errors)
    rev = df.iloc[::-1]
    assert any("ordenado" in e for e in quality.check_index(rev).errors)


# --- ADR-018: intradía real (M1/M5/H1/H4) ---

def _synthetic_yf_intraday(idx: pd.DatetimeIndex) -> pd.DataFrame:
    n = len(idx)
    close = np.linspace(0.66, 0.68, n)
    cols = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"], ["6A=F"]], names=["Price", "Ticker"])
    data = {
        ("Open", "6A=F"): close, ("High", "6A=F"): close + 0.001,
        ("Low", "6A=F"): close - 0.001, ("Close", "6A=F"): close, ("Volume", "6A=F"): [10.0] * n,
    }
    return pd.DataFrame(data, index=idx, columns=cols)


def test_resample_h4_derives_from_h1():
    idx = pd.date_range("2024-01-02 00:00", periods=8, freq="1h", tz="UTC")
    h1 = YahooFuturesSource._normalize(_synthetic_yf_intraday(idx))
    h4 = YahooFuturesSource._resample_h4(h1)
    assert len(h4) == 2  # 8 horas -> 2 velas de 4h
    assert (h4.index[1] - h4.index[0]) == pd.Timedelta("4h")


def test_fetch_clips_start_beyond_yahoo_lookback(monkeypatch):
    calls = []

    def fake_download(ticker, start, end, interval, progress, auto_adjust):
        calls.append(start)
        idx = pd.date_range(pd.Timestamp(start), periods=3, freq="5min", tz="UTC")
        return _synthetic_yf_intraday(idx)

    import yfinance
    monkeypatch.setattr(yfinance, "download", fake_download)

    src = YahooFuturesSource()
    far_past = datetime(2015, 1, 1)
    out = src.fetch("6A", "M5", far_past, datetime.now())
    assert not out.empty
    requested_start = pd.Timestamp(calls[0])
    # Yahoo M5 solo sirve ~60 dias -> el inicio real pedido NO debe ser 2015
    assert requested_start.year >= pd.Timestamp.now().year - 1


def test_fetch_m1_chunks_into_windows(monkeypatch):
    calls = []

    def fake_download(ticker, start, end, interval, progress, auto_adjust):
        calls.append((pd.Timestamp(start), pd.Timestamp(end)))
        idx = pd.date_range(pd.Timestamp(start), periods=2, freq="1min", tz="UTC")
        return _synthetic_yf_intraday(idx)

    import yfinance
    monkeypatch.setattr(yfinance, "download", fake_download)

    src = YahooFuturesSource()
    end = datetime.now()
    start = end - timedelta(days=20)  # > 7 dias -> debe encadenar varios requests
    out = src.fetch("6A", "M1", start, end)
    assert not out.empty
    assert len(calls) >= 3  # 20 dias / 7 dias por bloque
    for chunk_start, chunk_end in calls:
        assert (chunk_end - chunk_start) <= timedelta(days=7, hours=1)


def test_fetch_clips_end_fixed_in_the_past_to_recent_window(monkeypatch):
    """Reproduce el bug real: pedir H1 con `end` fijo hace ~1 año (config
    histórica del proyecto) fallaba porque Yahoo solo sirve una ventana
    intradía reciente que termina HOY, no un tramo fijo en el pasado."""
    calls = []

    def fake_download(ticker, start, end, interval, progress, auto_adjust):
        calls.append((pd.Timestamp(start), pd.Timestamp(end)))
        idx = pd.date_range(pd.Timestamp(start), periods=2, freq="1h", tz="UTC")
        return _synthetic_yf_intraday(idx)

    import yfinance
    monkeypatch.setattr(yfinance, "download", fake_download)

    src = YahooFuturesSource()
    start = datetime(2020, 7, 1)
    end_naive = datetime.now() - timedelta(days=365)  # fin fijo hace ~1 año, como en el log real
    out = src.fetch("6A", "H1", start, end_naive)
    assert not out.empty
    requested_start, requested_end = calls[0]
    requested_end = pd.Timestamp(requested_end).tz_localize("UTC")
    requested_start = pd.Timestamp(requested_start).tz_localize("UTC")
    end_requested = pd.Timestamp(end_naive).tz_localize("UTC")
    # el fin efectivo NO debe ser el de hace un año -> debe recortarse a "hoy"
    assert requested_end > end_requested + timedelta(days=300)
    assert requested_start < requested_end
