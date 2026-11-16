"""Adaptador para archivos DBN descargados MANUALMENTE de Databento (ADR-021).

Fuente: dataset GLBX.MDP3 (CME Globex), schema `ohlcv-1m`, símbolo continuo
`6A.v.0` (contrato de mayor volumen), tal como lo bajó el usuario desde el portal
de Databento (lote mensual `.dbn.zst` + `manifest.json` con sha256 por archivo).
No se descarga nada aquí: el usuario deja los archivos en
`data/manual_imports/databento/`.

Hechos verificados sobre estos datos (ver ADR-021):
  - Es el 6A REAL (futuro CME), no el proxy spot. `ts_event` = apertura de la barra, UTC.
  - Solo hay barra en los minutos con al menos una operación (no hay barras de relleno).
  - No trae bid/ask: no hay spread histórico. Los costos siguen el modelo de SPEC_COSTOS_6A.
  - El símbolo continuo `.v.0` cambia de contrato ~cada 3 meses, SIEMPRE a las 00:00 UTC
    (inicio de la sesión de Tokio que usa la estrategia). Los precios NO vienen ajustados:
    en cada roll hay un salto que es diferencial entre contratos (0.5 a 30 pips), no movimiento.
    Por eso se guardan `instrument_id` y `roll_adj` (ver `compute_roll_adjustment`).
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
from datetime import datetime

import numpy as np
import pandas as pd

from data import schema
from data.sources.base import DataSource

DEFAULT_IMPORT_DIR = "data/manual_imports/databento"
INSTRUMENT_ID = "instrument_id"
ROLL_ADJ = "roll_adj"
_MONTH_RE = re.compile(r"glbx-mdp3-(\d{8})-(\d{8})\.ohlcv-1m\.dbn\.zst$")


def verify_against_manifest(import_dir: str) -> list[str]:
    """Compara el sha256 de cada .dbn.zst contra el `manifest.json` de Databento si existe.

    Returns: lista de problemas (vacía = todo coincide o no hay manifest).
    """
    mpaths = sorted(glob.glob(os.path.join(import_dir, "manifest*.json")))  # un manifest por descarga
    if not mpaths:
        return []
    expected: dict[str, str] = {}
    for mp in mpaths:
        expected.update({f["filename"]: f["hash"].split(":")[-1] for f in json.load(open(mp))["files"]})
    problems = []
    for p in sorted(glob.glob(os.path.join(import_dir, "*.dbn.zst"))):
        name = os.path.basename(p)
        if name not in expected:
            continue
        h = hashlib.sha256(open(p, "rb").read()).hexdigest()
        if h != expected[name]:
            problems.append(f"{name}: sha256 no coincide con el manifest de Databento")
    return problems


def read_dbn_files(import_dir: str = DEFAULT_IMPORT_DIR) -> pd.DataFrame:
    """Lee todos los `.dbn.zst` de la carpeta y devuelve M1 en esquema canónico + instrument_id."""
    import databento as db  # import local: dependencia opcional, solo para esta fuente

    paths = sorted(p for p in glob.glob(os.path.join(import_dir, "*.dbn.zst")) if _MONTH_RE.search(p))
    if not paths:
        raise FileNotFoundError(
            f"No encontré archivos glbx-mdp3-*.ohlcv-1m.dbn.zst en {import_dir!r}. "
            "Copia ahí los archivos descargados de Databento (y su manifest.json)."
        )
    frames = []
    for p in paths:
        d = db.DBNStore.from_file(p).to_df(price_type="float", pretty_ts=True, map_symbols=False)
        frames.append(d.reset_index())
    m = pd.concat(frames, ignore_index=True)
    m = m.rename(columns={"ts_event": schema.TIMESTAMP})
    m[schema.TIMESTAMP] = pd.to_datetime(m[schema.TIMESTAMP], utc=True)
    m = m.sort_values(schema.TIMESTAMP).drop_duplicates(schema.TIMESTAMP, keep="first")
    out = m.set_index(schema.TIMESTAMP)[
        [schema.OPEN, schema.HIGH, schema.LOW, schema.CLOSE, schema.VOLUME, INSTRUMENT_ID]
    ].copy()
    out[schema.VOLUME] = out[schema.VOLUME].astype("float64")
    out[INSTRUMENT_ID] = out[INSTRUMENT_ID].astype("int64")
    return out


def compute_roll_adjustment(m1: pd.DataFrame) -> pd.Series:
    """Offset ADITIVO por barra para volver continua la serie (ajuste por diferencia hacia atrás).

    `precio_ajustado = precio + roll_adj`. Las barras del contrato más reciente tienen 0;
    las anteriores acumulan el salto de cada roll posterior, de modo que niveles viejos
    (PDH/PDL, swings, equal highs) quedan en los mismos términos que el contrato vigente.

    Supuesto declarado: salto = open de la 1ª barra del contrato nuevo - close de la última
    del anterior. Incluye el movimiento real de ese intervalo (normalmente 1 minuto). En el roll
    del 2023-06-18 el intervalo cruza un fin de semana (el contrato viejo vence el 16-jun), así
    que ese ajuste incluye el gap de fin de semana: imperfecto, afecta 1 sola sesión.
    """
    chg = m1[INSTRUMENT_ID].ne(m1[INSTRUMENT_ID].shift())
    jump = pd.Series(0.0, index=m1.index)
    jump[chg] = (m1[schema.OPEN] - m1[schema.CLOSE].shift())[chg]
    jump.iloc[0] = 0.0
    # El ajuste de una barra = suma de los saltos de rolls POSTERIORES a ella, con signo negativo
    # (para llevar el contrato viejo al nivel del nuevo hay que sumar +salto).
    total_after = jump.iloc[::-1].cumsum().iloc[::-1] - jump  # saltos estrictamente posteriores
    return total_after.rename(ROLL_ADJ)


def resample_ohlcv(m1: pd.DataFrame, freq: str) -> pd.DataFrame:
    """M1 -> M5/H1/etc. Etiqueta = apertura de la barra (igual que Dukascopy). Sin barras vacías."""
    agg = {
        schema.OPEN: "first", schema.HIGH: "max", schema.LOW: "min", schema.CLOSE: "last",
        schema.VOLUME: "sum", INSTRUMENT_ID: "last", ROLL_ADJ: "last",
    }
    r = m1.resample(freq, label="left", closed="left").agg(agg).dropna(subset=[schema.CLOSE])
    r[INSTRUMENT_ID] = r[INSTRUMENT_ID].astype("int64")
    r.index.name = schema.TIMESTAMP
    return r


class DatabentoDBNSource(DataSource):
    """6A real desde archivos DBN locales (ADR-021). Solo entrega M1; M5/H1 se derivan por resample."""

    name = "databento_dbn"

    def __init__(self, import_dir: str = DEFAULT_IMPORT_DIR):
        self.import_dir = import_dir

    def fetch(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        if symbol != "6A":
            raise ValueError("databento_dbn solo cubre 6A (ADR-021)")
        m1 = read_dbn_files(self.import_dir)
        m1[ROLL_ADJ] = compute_roll_adjustment(m1)
        df = m1 if timeframe == "M1" else resample_ohlcv(m1, schema.freq_for(timeframe))
        s, e = pd.Timestamp(start), pd.Timestamp(end)
        s = s.tz_localize("UTC") if s.tz is None else s.tz_convert("UTC")
        e = e.tz_localize("UTC") if e.tz is None else e.tz_convert("UTC")
        return df[(df.index >= s) & (df.index <= e)]
