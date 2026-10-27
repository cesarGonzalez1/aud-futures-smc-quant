"""Tests de las piezas nuevas de niveles para V5: día completo y equals recientes
(ADR-011)."""

from __future__ import annotations

import pandas as pd

from data import schema
from features import levels


def test_day_extremes_resets_at_utc_midnight():
    idx = pd.date_range("2024-01-01 22:00", periods=10, freq="1h", tz="UTC")
    high = [1.10, 1.12, 1.20, 1.05, 1.08, 1.15, 1.02, 1.30, 1.01, 1.25]
    low = [1.00, 1.02, 1.05, 0.95, 1.00, 1.05, 0.90, 1.10, 0.85, 1.15]
    df = pd.DataFrame({schema.OPEN: low, schema.HIGH: high, schema.LOW: low,
                       schema.CLOSE: high}, index=idx)
    df.index.name = schema.TIMESTAMP
    out = levels.add_day_extremes(df)
    # idx[0]=22:00, idx[1]=23:00 (mismo dia calendario) -> expanding.
    assert out["day_hi"].iloc[0] == 1.10
    assert out["day_hi"].iloc[1] == 1.12
    # idx[2] = 2024-01-02 00:00 -> nuevo dia calendario UTC -> REINICIA.
    assert out["day_hi"].iloc[2] == 1.20
    assert out["day_lo"].iloc[2] == 1.05


def test_recent_equal_flag_persists_within_window_and_resets_next_cycle():
    idx = pd.date_range("2024-01-01 20:00", "2024-01-03 06:00", freq="1h", tz="UTC")
    n = len(idx)
    df = pd.DataFrame({
        schema.OPEN: [1.0] * n, schema.HIGH: [1.01] * n, schema.LOW: [0.99] * n, schema.CLOSE: [1.0] * n,
        "equal_high": [False] * n, "equal_low": [False] * n,
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    df.loc[pd.Timestamp("2024-01-01 23:00", tz="UTC"), "equal_high"] = True

    out = levels.add_recent_equal_flag(df, window_start_hour_utc=22, entry_session_end_hour_utc=4)

    # Dentro de la misma ventana (22:00 dia1 -> 04:00 dia2), debe seguir True.
    assert bool(out.loc[pd.Timestamp("2024-01-02 02:00", tz="UTC"), "equal_high_recent"])
    # Fuera de la ventana (10:00), inactiva -> False.
    assert not bool(out.loc[pd.Timestamp("2024-01-02 10:00", tz="UTC"), "equal_high_recent"])
    # En el ciclo SIGUIENTE (22:00 dia2 en adelante) no debe arrastrar el flag viejo.
    nxt = pd.Timestamp("2024-01-02 23:00", tz="UTC")
    if nxt in out.index:
        assert not bool(out.loc[nxt, "equal_high_recent"])
