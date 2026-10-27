"""Persistencia inmutable en Parquet + escritura atómica del par (parquet, manifest).

El dato crudo es inmutable (Data Philosophy del proyecto). Este módulo escribe el
Parquet y su manifest juntos, y siempre calcula el sha256 DESPUÉS de escribir el
Parquet final para que el manifest describa exactamente el archivo en disco.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from data import schema
from data.storage.manifest import Manifest, sha256_file

PARQUET_NAME = "data.parquet"


def dataset_dir(base: str | Path, symbol: str, timeframe: str) -> Path:
    """Ruta convencional de un dataset: <base>/<symbol>/<timeframe>/ (sección 10)."""
    return Path(base) / symbol / timeframe


def write_dataset(
    df: pd.DataFrame,
    *,
    base: str | Path,
    source: str,
    symbol: str,
    timeframe: str,
    download_timestamp: str,
    parent_sha256: str | None = None,
    role: str = schema.ROLE_CONTEXT,
) -> Manifest:
    """Escribe un dataset OHLCV validado + su manifest de versión.

    El `download_timestamp` se recibe como parámetro (no se genera aquí) para
    mantener el pipeline determinista y reproducible: el llamador decide el sello
    de tiempo, típicamente leído del reloj una sola vez al inicio de la ingesta.

    Args:
        df: DataFrame en esquema canónico (índice UTC ordenado). Se asume ya
            validado por data.validation.quality.
        base: raíz de almacenamiento (ej. "data/raw").
        source: fuente ("dukascopy", "stooq", ...).
        symbol: símbolo (ej. "AUDUSD").
        timeframe: timeframe (ej. "H1").
        download_timestamp: ISO 8601 UTC del momento de ingesta.
        parent_sha256: sha256 del dataset padre si es derivado; None si es crudo.
        role: rol del instrumento (ADR-006): "real", "proxy" o "context".

    Returns:
        El Manifest escrito.

    Raises:
        ValueError: si el índice no es tz-aware UTC u ordenado (defensa en
            profundidad; la validación de calidad ya debió garantizarlo).
    """
    if df.index.name != schema.TIMESTAMP:
        raise ValueError(f"El índice debe llamarse {schema.TIMESTAMP!r}")
    if df.index.tz is None:
        raise ValueError("El índice debe ser tz-aware en UTC (sección 11)")
    if not df.index.is_monotonic_increasing:
        raise ValueError("El índice debe estar ordenado ascendente")

    out_dir = dataset_dir(base, symbol, timeframe)
    out_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = out_dir / PARQUET_NAME

    df.to_parquet(parquet_path, engine="pyarrow", index=True)

    manifest = Manifest(
        source=source,
        symbol=symbol,
        timeframe=timeframe,
        date_range=(
            df.index[0].date().isoformat(),
            df.index[-1].date().isoformat(),
        ),
        download_timestamp=download_timestamp,
        sha256=sha256_file(parquet_path),
        row_count=int(len(df)),
        parent_sha256=parent_sha256,
        role=schema.validate_role(role),
    )
    manifest.write(out_dir)
    return manifest


def read_dataset(base: str | Path, symbol: str, timeframe: str) -> pd.DataFrame:
    """Lee un dataset desde su carpeta convencional.

    Raises:
        FileNotFoundError: si el parquet no existe.
    """
    parquet_path = dataset_dir(base, symbol, timeframe) / PARQUET_NAME
    return pd.read_parquet(parquet_path, engine="pyarrow")
