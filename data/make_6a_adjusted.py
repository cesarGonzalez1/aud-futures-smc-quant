"""Deriva `6A_ADJ` (6A real con precios ajustados por roll) desde Databento (ADR-021, SPEC_V17).

Lee data/raw/6A/{M5,H1} (Databento, con columna `roll_adj`) y escribe data/raw/6A_ADJ/{M5,H1,D1}:
OHLC ajustados (`precio + roll_adj`), para que swings, sweeps, FVG y PDH/PDL no crucen saltos de roll.
D1 se agrega desde H1 por día calendario UTC (misma convención que el D1 del proxy AUDUSD).
SIN columna `spread` (Databento no trae bid/ask): el costo viene del modelo real de SPEC_COSTOS_6A.
El precio ajustado NO es el precio histórico real (ver ADR-021, limitación 2).

Uso: python -m data.make_6a_adjusted
"""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from data import ingest, schema
from data.storage import parquet_store
from data.storage.manifest import read_manifest

SYMBOL_ADJ = "6A_ADJ"


def adjust_prices(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica `roll_adj` a OHLC. Devuelve esquema canónico (OHLCV) + instrument_id."""
    out = df.copy()
    for c in schema.OHLC_COLUMNS:
        out[c] = out[c] + out["roll_adj"]
    return out[[*schema.OHLCV_COLUMNS, "instrument_id"]]


def to_daily_utc(h1: pd.DataFrame) -> pd.DataFrame:
    agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum", "instrument_id": "last"}
    d = h1.resample("1D", label="left", closed="left").agg(agg).dropna(subset=["close"])
    d.index.name = schema.TIMESTAMP
    return d


def main() -> None:
    config = ingest.load_config()
    raw = config["paths"]["raw"]
    ts = datetime.now(timezone.utc).isoformat()
    h1_adj = None
    for tf in ("M5", "H1"):
        df = parquet_store.read_dataset(raw, "6A", tf)
        parent = read_manifest(parquet_store.dataset_dir(raw, "6A", tf)).sha256
        adj = adjust_prices(df)
        if tf == "H1":
            h1_adj = adj
        parquet_store.write_dataset(adj, base=raw, symbol=SYMBOL_ADJ, timeframe=tf, source="databento_dbn_adjusted",
                                    role=schema.ROLE_REAL, download_timestamp=ts, parent_sha256=parent)
        print(f"{SYMBOL_ADJ} {tf}: {len(adj)} barras")
    d1 = to_daily_utc(h1_adj)
    parent = read_manifest(parquet_store.dataset_dir(raw, "6A", "H1")).sha256
    parquet_store.write_dataset(d1, base=raw, symbol=SYMBOL_ADJ, timeframe="D1", source="databento_dbn_adjusted",
                                role=schema.ROLE_REAL, download_timestamp=ts, parent_sha256=parent)
    print(f"{SYMBOL_ADJ} D1: {len(d1)} barras")


if __name__ == "__main__":
    main()
