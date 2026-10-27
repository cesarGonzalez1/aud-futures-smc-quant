"""Tests del trailing stop por estructura (ADR-013, la regla real del usuario:
mueve el stop al PENÚLTIMO swing confirmado, nunca al más reciente)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from strategy.trade_management import _simulate_exit_trailing_structure


def _short_setup():
    idx = pd.date_range("2024-01-01 00:00", periods=30, freq="5min", tz="UTC")
    n = len(idx)
    high = np.linspace(1.00, 0.85, n)
    low = high - 0.01
    sh_conf = [False] * n
    sh_price = [np.nan] * n
    sh_conf[5], sh_price[5] = True, 0.98
    sh_conf[12], sh_price[12] = True, 0.96
    sh_conf[20], sh_price[20] = True, 0.94
    df = pd.DataFrame({
        schema.OPEN: high, schema.HIGH: high.tolist(), schema.LOW: low.tolist(), schema.CLOSE: high.tolist(),
        "swing_high_confirmed": sh_conf, "last_swing_high": sh_price,
        "swing_low_confirmed": [False] * n, "last_swing_low": [np.nan] * n,
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    return df


def test_with_two_impulses_stop_uses_the_first_not_the_second():
    df = _short_setup()
    h = df[schema.HIGH].tolist()
    h[13] = 0.985  # tras el 2do impulso (barra 12), toca el nivel del PRIMER swing (0.98)
    df[schema.HIGH] = h
    _, exit_price, outcome = _simulate_exit_trailing_structure(
        df, entry_pos=0, side="short", initial_stop=1.10, target=0.80, lag_swings=1)
    assert outcome == "trailing_stop"
    assert exit_price == 0.98


def test_touching_the_most_recent_swing_does_not_trigger_exit():
    df = _short_setup()
    h = df[schema.HIGH].tolist()
    h[13] = 0.965  # toca el swing MÁS reciente (0.96), pero el nivel activo sigue siendo 0.98
    df[schema.HIGH] = h
    _, _, outcome = _simulate_exit_trailing_structure(
        df, entry_pos=0, side="short", initial_stop=1.10, target=0.80, lag_swings=1)
    assert outcome not in ("trailing_stop", "stop")


def test_after_third_impulse_stop_advances_to_the_second():
    df = _short_setup()
    h = df[schema.HIGH].tolist()
    h[22] = 0.965  # tras el 3er impulso (barra 20), el nivel activo avanza a 0.96 (el segundo)
    df[schema.HIGH] = h
    _, exit_price, outcome = _simulate_exit_trailing_structure(
        df, entry_pos=0, side="short", initial_stop=1.10, target=0.80, lag_swings=1)
    assert outcome == "trailing_stop"
    assert exit_price == 0.96


def test_stop_never_loosens():
    # Si un swing nuevo confirma en un nivel PEOR (más alto para short), el stop NO retrocede.
    df = _short_setup()
    sh_price = df["last_swing_high"].tolist()
    sh_price[12] = 0.99  # peor que el primer swing (0.98) -- no deberia empeorar el stop
    df["last_swing_high"] = sh_price
    h = df[schema.HIGH].tolist()
    h[13] = 0.985
    df[schema.HIGH] = h
    _, exit_price, outcome = _simulate_exit_trailing_structure(
        df, entry_pos=0, side="short", initial_stop=1.10, target=0.80, lag_swings=1)
    # Con 2 impulsos (0.98, 0.99), el candidato es 0.98 (el mas antiguo) -- igual sale ahi.
    assert outcome == "trailing_stop"
    assert exit_price == 0.98


def test_target_reached_before_any_trail_trigger():
    df = _short_setup()
    h = df[schema.HIGH].tolist()
    df[schema.HIGH] = h
    lo = df[schema.LOW].tolist()
    lo[3] = 0.80  # llega al target antes de que se confirme ningun impulso
    df[schema.LOW] = lo
    _, exit_price, outcome = _simulate_exit_trailing_structure(
        df, entry_pos=0, side="short", initial_stop=1.10, target=0.80, lag_swings=1)
    assert outcome == "target"
    assert exit_price == 0.80
