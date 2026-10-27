"""Orquestador de feature engineering (Fase 2, sección 7).

Lee el dataset crudo validado de `data/raw/` (Fase 1), calcula todas las familias
de features y escribe un dataset derivado en `data/features/` con su manifest,
cuyo `parent_sha256` apunta al crudo del que proviene (cadena de trazabilidad,
sección 10). Los features se calculan sobre AUD/USD H1 (timeframe principal); D1
y cross-asset entran como contexto.

Ejecución:  python -m features.build
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from data import ingest, schema
from data.storage import parquet_store
from data.storage.manifest import Manifest, read_manifest
from features import cross_asset, indicators, realized_vol, sessions, structure


def build_features(config: dict | None = None) -> Manifest:
    """Construye el dataset de features de AUD/USD H1 y lo persiste.

    Returns:
        El Manifest del dataset de features escrito (con parent_sha256 del crudo).
    """
    config = config or ingest.load_config()
    raw = config["paths"]["raw"]
    feat_base = config["paths"]["features"]
    symbol = config["instruments"]["primary"]["symbol"]
    tf = "H1"

    df = parquet_store.read_dataset(raw, symbol, tf)
    raw_manifest = read_manifest(parquet_store.dataset_dir(raw, symbol, tf))

    # Familias de features (sección 7).
    df = indicators.add_trend_momentum(df)
    df = indicators.add_volatility(df)
    df = sessions.add_sessions(df, config["sessions"])
    df = structure.add_structure(df)
    df = realized_vol.add_realized_vol(df)
    df = realized_vol.add_forward_vol_target(df)  # TARGET (usa futuro, sección 2)

    # Cross-asset (ADR-005): XAU H1, DXY D1, diferencial de tasas.
    xau = parquet_store.read_dataset(raw, "XAUUSD", "H1")
    dxy = parquet_store.read_dataset(raw, "DXY", "D1")
    rates_csv = config["instruments"]["rates_table"]["path"]
    df = cross_asset.add_cross_asset(df, xau=xau, dxy=dxy, rates_csv=rates_csv)

    download_ts = datetime.now(timezone.utc).isoformat()
    # El rol se hereda del crudo del que deriva: AUD/USD H1 es `proxy` (ADR-006),
    # así que el dataset de features de estructura intradía queda marcado proxy,
    # nunca como si fuera el activo real 6A.
    return parquet_store.write_dataset(
        df,
        base=feat_base,
        source="derived",
        symbol=symbol,
        timeframe=tf,
        download_timestamp=download_ts,
        parent_sha256=raw_manifest.sha256,
        role=raw_manifest.role,
    )


def main() -> None:
    man = build_features()
    print("=== Features construidos (Fase 2) ===")
    print(f"  {man.symbol} {man.timeframe}: {man.row_count} filas  role={man.role}")
    print(f"  sha256={man.sha256[:12]}  parent(raw)={man.parent_sha256[:12]}")


if __name__ == "__main__":
    main()
