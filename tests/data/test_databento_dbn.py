"""Tests del adaptador Databento (ADR-021) con datos sintéticos de respuesta conocida."""
import numpy as np
import pandas as pd

from data.sources import databento_dbn as dbn


def _m1():
    idx = pd.date_range("2024-03-15 23:58", periods=6, freq="1min", tz="UTC", name="timestamp")
    # contrato 1 hasta 00:00 (excl.); contrato 2 desde 00:00 con un salto de +0.0010
    close = [0.6500, 0.6502, 0.6600, 0.6601, 0.6602, 0.6603]
    open_ = [0.6499, 0.6500, 0.6512, 0.6600, 0.6601, 0.6602]
    df = pd.DataFrame({"open": open_, "high": np.add(close, 0.0002), "low": np.subtract(close, 0.0002),
                       "close": close, "volume": 10.0, "instrument_id": [1, 1, 2, 2, 2, 2]}, index=idx)
    return df


def test_roll_adj_es_cero_en_contrato_vigente_y_suma_salto_en_el_viejo():
    m1 = _m1()
    adj = dbn.compute_roll_adjustment(m1)
    assert (adj.iloc[2:] == 0).all()                       # contrato nuevo: sin ajuste
    salto = m1["open"].iloc[2] - m1["close"].iloc[1]       # 0.6512 - 0.6502 = 0.0010
    assert np.allclose(adj.iloc[:2], salto)


def test_serie_ajustada_no_tiene_salto_en_el_roll():
    m1 = _m1()
    m1["roll_adj"] = dbn.compute_roll_adjustment(m1)
    a = m1["close"] + m1["roll_adj"]
    # el salto (close->open de la barra del roll) desaparece: open_nuevo - (close_viejo + adj) == 0
    assert abs(m1["open"].iloc[2] - a.iloc[1]) < 1e-12


def test_resample_usa_apertura_como_etiqueta_y_agrega_ohlc():
    idx = pd.date_range("2024-01-02 00:00", periods=10, freq="1min", tz="UTC", name="timestamp")
    df = pd.DataFrame({"open": np.arange(10) + 1.0, "high": np.arange(10) + 2.0, "low": np.arange(10) + 0.5,
                       "close": np.arange(10) + 1.5, "volume": 1.0, "instrument_id": 7, "roll_adj": 0.0}, index=idx)
    r = dbn.resample_ohlcv(df, "5min")
    assert list(r.index) == [pd.Timestamp("2024-01-02 00:00", tz="UTC"), pd.Timestamp("2024-01-02 00:05", tz="UTC")]
    assert r["open"].iloc[0] == 1.0 and r["close"].iloc[0] == 5.5 and r["high"].iloc[0] == 6.0
    assert r["low"].iloc[0] == 0.5 and r["volume"].iloc[0] == 5.0
