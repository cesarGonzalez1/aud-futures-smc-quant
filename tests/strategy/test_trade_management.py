"""Tests de la gestión de breakeven móvil (ADR-012)."""

from __future__ import annotations

import pandas as pd

from data import schema
from strategy.liquidity_sweep_ifvg import Trade
from strategy.trade_management import _simulate_exit_breakeven, apply_breakeven_management


def _bars(n=20):
    idx = pd.date_range("2024-01-01 00:00", periods=n, freq="5min", tz="UTC")
    return idx, n


def test_breakeven_rescues_trade_that_reverses_after_moving_in_favor():
    idx, n = _bars()
    high = [1.005] * n
    low = [1.001] * n
    high[3] = 1.05    # se mueve a favor lo suficiente para disparar breakeven (>=0.4R)
    low[6] = 0.95      # luego cae muy por debajo del stop original (0.90), pero el
                        # breakeven ya deberia haber movido el stop a 1.00 antes de esto
    df = pd.DataFrame({schema.OPEN: [1.0] * n, schema.HIGH: high, schema.LOW: low,
                       schema.CLOSE: [1.0] * n}, index=idx)
    df.index.name = schema.TIMESTAMP

    exit_time, exit_price, outcome = _simulate_exit_breakeven(
        df, entry_pos=0, side="long", initial_stop=0.90, target=1.20,
        entry_price=1.00, breakeven_trigger_r=0.4,
    )
    assert outcome == "breakeven"
    assert exit_price == 1.00  # sale en breakeven, NO en el stop original 0.90


def test_no_breakeven_trigger_keeps_original_stop_behavior():
    idx, n = _bars()
    high = [1.005] * n
    low = [1.001] * n
    low[5] = 0.85  # cae directo, nunca se movio a favor lo suficiente para el breakeven
    df = pd.DataFrame({schema.OPEN: [1.0] * n, schema.HIGH: high, schema.LOW: low,
                       schema.CLOSE: [1.0] * n}, index=idx)
    df.index.name = schema.TIMESTAMP

    _, exit_price, outcome = _simulate_exit_breakeven(
        df, entry_pos=0, side="long", initial_stop=0.90, target=1.20,
        entry_price=1.00, breakeven_trigger_r=0.4,
    )
    assert outcome == "stop"
    assert exit_price == 0.90  # comportamiento identico al de la version sin gestion


def test_clean_move_to_target_is_unaffected_by_breakeven_logic():
    idx, n = _bars()
    high = [1.005] * n
    low = [1.001] * n  # nunca baja de la entrada
    high[2] = 1.20
    df = pd.DataFrame({schema.OPEN: [1.0] * n, schema.HIGH: high, schema.LOW: low,
                       schema.CLOSE: [1.0] * n}, index=idx)
    df.index.name = schema.TIMESTAMP

    _, exit_price, outcome = _simulate_exit_breakeven(
        df, entry_pos=0, side="long", initial_stop=0.90, target=1.20,
        entry_price=1.00, breakeven_trigger_r=0.4,
    )
    assert outcome == "target"
    assert exit_price == 1.20


def test_apply_breakeven_management_preserves_entry_stop_target():
    idx, n = _bars()
    high = [1.005] * n
    low = [1.001] * n
    high[2] = 1.20
    df = pd.DataFrame({schema.OPEN: [1.0] * n, schema.HIGH: high, schema.LOW: low,
                       schema.CLOSE: [1.0] * n}, index=idx)
    df.index.name = schema.TIMESTAMP

    t = Trade(entry_time=idx[0].isoformat(), side="long", entry_price=1.00, stop=0.90,
              target=1.20, exit_time=idx[-1].isoformat(), exit_price=1.0,
              outcome="open", r_multiple=0.0, cohort="2024")
    out = apply_breakeven_management([t], df, breakeven_trigger_r=0.4)

    assert len(out) == 1
    assert out[0].entry_price == 1.00
    assert out[0].stop == 0.90     # el stop INICIAL guardado no cambia
    assert out[0].target == 1.20
    assert out[0].outcome == "target"
    assert out[0].r_multiple == 2.0  # (1.20-1.00)/(1.00-0.90) = 2.0
