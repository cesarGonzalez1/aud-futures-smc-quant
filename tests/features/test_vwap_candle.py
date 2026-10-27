"""Tests de VWAP de sesión y vela diaria (V12): valores conocidos + anti-look-ahead."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features.daily_candle import add_trading_day_candle
from features.vwap import add_session_vwap, session_id


def _bars(start, n, closes, vol=100.0, freq="5min"):
    idx = pd.date_range(start, periods=n, freq=freq, tz="UTC", name=schema.TIMESTAMP)
    c = np.asarray(closes, dtype=float)
    return pd.DataFrame({schema.OPEN: c, schema.HIGH: c + 0.001, schema.LOW: c - 0.001,
                         schema.CLOSE: c, schema.VOLUME: vol}, index=idx)


def test_vwap_constant_price_has_zero_width():
    df = _bars("2024-01-09 00:00", 10, [0.66] * 10)
    out = add_session_vwap(df)
    assert np.allclose(out["vwap"], 0.66)           # hlc3 de (c+.001, c-.001, c) = c
    assert np.allclose(out["vwap_up"], out["vwap_lo"])


def test_vwap_two_prices_known_value():
    df = _bars("2024-01-09 00:00", 2, [1.0, 2.0])   # vol igual → vwap=1.5, sd=0.5
    out = add_session_vwap(df)
    assert np.isclose(out["vwap"].iloc[1], 1.5)
    assert np.isclose(out["vwap_up"].iloc[1], 2.0)
    assert np.isclose(out["vwap_lo"].iloc[1], 1.0)


def test_vwap_resets_at_cme_open_17_chicago():
    # Enero: CST = UTC-6 → 17:00 CT = 23:00 UTC. La barra de 23:00 abre sesión nueva.
    df = _bars("2024-01-09 22:00", 24, [1.0] * 12 + [5.0] * 12)  # 22:00-22:55 | 23:00 en adelante
    out = add_session_vwap(df)
    assert np.isclose(out["vwap"].iloc[11], 1.0)     # sesión vieja
    assert np.isclose(out["vwap"].iloc[12], 5.0)     # reinicio en 23:00 UTC → solo precio 5


def test_vwap_is_point_in_time():
    rng = np.random.default_rng(0)
    df = _bars("2024-01-09 00:00", 80, 0.66 + rng.normal(0, 0.002, 80).cumsum() / 10,
               vol=rng.integers(50, 200, 80))
    full = add_session_vwap(df)
    for t in (20, 40, 79):
        part = add_session_vwap(df.iloc[: t + 1])
        assert np.allclose(part[["vwap", "vwap_up", "vwap_lo"]].iloc[-1],
                           full[["vwap", "vwap_up", "vwap_lo"]].iloc[t])


def test_session_id_boundary():
    idx = pd.DatetimeIndex(["2024-01-09 22:55", "2024-01-09 23:00"], tz="UTC")
    s = session_id(idx)
    assert s[0] != s[1]


def test_candle_prev_and_today_dir():
    # Sesión A (abre 2024-01-08 23:00 UTC): sube. Sesión B (abre 2024-01-09 23:00): baja.
    a = _bars("2024-01-08 23:00", 12, np.linspace(1.0, 1.1, 12))
    b = _bars("2024-01-09 23:00", 12, np.linspace(1.1, 1.0, 12))
    df = pd.concat([a, b])
    out = add_trading_day_candle(df)
    assert (out["prev_dir"].iloc[:12] == 0).all()                  # sin sesión previa
    assert (out["prev_dir"].iloc[12:] == 1).all()                  # A fue alcista
    assert out["today_dir"].iloc[-1] == -1                         # B va bajista
    assert out["today_dir"].iloc[1] == 1                           # A va subiendo


def test_candle_today_dir_is_point_in_time():
    a = _bars("2024-01-08 23:00", 12, np.linspace(1.0, 1.1, 12))
    b = _bars("2024-01-09 23:00", 12, np.linspace(1.1, 1.0, 12))
    df = pd.concat([a, b])
    full = add_trading_day_candle(df)
    for t in (5, 15, 23):
        part = add_trading_day_candle(df.iloc[: t + 1])
        assert part[["today_dir", "prev_dir"]].iloc[-1].tolist() == full[["today_dir", "prev_dir"]].iloc[t].tolist()
