"""Tests de features V2 (ADR-008): order block, PWH/PWL, equal levels, acumulación."""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from features import levels, structure


def _ohlc(rows, freq="1h"):
    idx = pd.date_range("2024-01-01", periods=len(rows), freq=freq, tz="UTC")
    df = pd.DataFrame(rows, columns=[schema.OPEN, schema.HIGH, schema.LOW, schema.CLOSE], index=idx)
    df.index.name = schema.TIMESTAMP
    return df


# --- Order block ---

def test_order_block_bullish_detected_and_mitigated():
    # Vela bajista (idx3) seguida de un desplazamiento alcista fuerte que rompe el
    # swing high previo => OB alcista en idx3. Luego un cierre por debajo lo mitiga.
    rows = [
        [10, 11, 9, 10.5],   # 0
        [10.5, 12, 10, 11],  # 1  swing high se formará aquí
        [11, 11.5, 10.5, 11],# 2
        [11, 11.2, 10.0, 10.2],  # 3 vela bajista (OB candidate), close<open
        [10.2, 14, 10.2, 13.8],  # 4 desplazamiento alcista fuerte
        [13.8, 15, 13.5, 14.8],  # 5
        [14.8, 15, 9.0, 9.2],    # 6 cierre 9.2 < OB low(10.0) => mitiga
    ]
    df = _ohlc(rows)
    df["atr"] = 0.5
    df = structure.add_structure(df, k=1, sweep_lookback=50)
    out = structure.add_order_blocks(df, displacement_bars=2, displacement_atr=1.5)
    assert out["ob_bull"].any()
    ob_idx = np.where(out["ob_bull"].to_numpy())[0][0]
    assert df[schema.CLOSE].iloc[ob_idx] < df[schema.OPEN].iloc[ob_idx]  # vela bajista
    # Tras la mitigación (idx6) la zona vigente desaparece.
    assert np.isnan(out["ob_bull_low"].iloc[6])


def test_order_block_requires_displacement_size():
    # Mismo patrón pero rango pequeño (< 1.5*ATR con ATR grande) => sin OB.
    rows = [[10, 10.1, 9.9, 10], [10, 10.1, 9.9, 10], [10, 10.1, 9.8, 9.9],
            [9.9, 10.05, 9.85, 10.0], [10, 10.1, 9.9, 10.05]]
    df = _ohlc(rows)
    df["atr"] = 5.0  # umbral enorme
    df = structure.add_structure(df, k=1)
    out = structure.add_order_blocks(df, displacement_bars=2, displacement_atr=1.5)
    assert not out["ob_bull"].any()
    assert not out["ob_bear"].any()


# --- PWH/PWL ---

def test_pwh_pwl_uses_previous_week():
    days = pd.date_range("2024-01-01", periods=21, freq="1D", tz="UTC")  # 3 semanas
    d1 = pd.DataFrame({
        schema.OPEN: 1.0, schema.HIGH: np.arange(21) * 0.1 + 1.0,
        schema.LOW: 1.0 - np.arange(21) * 0.01, schema.CLOSE: 1.0,
    }, index=days)
    d1.index.name = schema.TIMESTAMP
    intr = d1.copy()  # usar D1 como "intradía" para el test
    out = levels.add_pwh_pwl(intr, d1)
    # Semana 1 (primeros 7 días) no tiene semana previa => NaN.
    assert np.isnan(out["pwh"].iloc[0])
    # Semana 2 debe tener el PWH = max de la semana 1.
    wk2 = out.iloc[7:14]
    assert (wk2["pwh"] == d1[schema.HIGH].iloc[:7].max()).all()


# --- Equal levels ---

def test_equal_highs_detected_within_tolerance():
    # Dos swing highs casi iguales dentro de 0.1*ATR => equal_high en el segundo.
    n = 12
    rows = [[10, 10.2, 9.8, 10]] * n
    df = _ohlc([list(r) for r in rows])
    # forzar dos picos iguales
    df.iloc[3, df.columns.get_loc(schema.HIGH)] = 12.0
    df.iloc[8, df.columns.get_loc(schema.HIGH)] = 12.02
    df["atr"] = 1.0  # tol = 0.1
    df = structure.add_structure(df, k=2)
    out = levels.add_equal_levels(df, tol_atr_frac=0.1, lookback=50)
    assert out["equal_high"].any()


# --- Acumulación ---

def test_accumulation_requires_consecutive_calm():
    n = 10
    df = _ohlc([[1, 1.1, 0.9, 1.0]] * n)
    df["regime_vol"] = ["alta"] * 3 + ["baja"] * 7
    df["regime_trend"] = "trending"
    out = levels.add_accumulation_range(df, window=6)
    # Solo cuando hay 6 barras 'baja' consecutivas (índices 3..8) empieza a marcar.
    assert not out["in_accumulation"].iloc[7]   # solo 5 baja consecutivas hasta idx7
    assert out["in_accumulation"].iloc[8]        # 6 baja consecutivas (idx3..8)
    assert out["acc_low"].iloc[8] == 0.9 and out["acc_high"].iloc[8] == 1.1
