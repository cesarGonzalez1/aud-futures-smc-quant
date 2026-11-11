"""Ingesta puntual de 6A real desde archivos DBN de Databento (ADR-021).

No toca `make ingest` ni config/settings.yaml (fuente manual, igual que ADR-020).
Escribe M1, M5 y H1 en data/raw/6A/<tf>/ con manifest sha256 (role=real).

Uso:
  python -m data.import_databento
  python -m data.import_databento --dir data/manual_imports/databento
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from data import ingest, schema
from data.sources import databento_dbn as dbn
from data.storage import parquet_store
from data.validation import quality


def main() -> None:
    args = sys.argv[1:]
    import_dir = args[args.index("--dir") + 1] if "--dir" in args else dbn.DEFAULT_IMPORT_DIR
    problems = dbn.verify_against_manifest(import_dir)
    if problems:
        print("sha256 FALLÓ:\n  " + "\n  ".join(problems))
        raise SystemExit(1)
    print("sha256 de los archivos coincide con el manifest de Databento (o no hay manifest).")

    config = ingest.load_config()
    src = dbn.DatabentoDBNSource(import_dir)
    start, end = datetime(2015, 1, 1), datetime(2100, 1, 1)
    download_ts = datetime.now(timezone.utc).isoformat()

    for tf in ("M1", "M5", "H1"):
        df = src.fetch("6A", tf, start, end)
        print(f"{tf}: {len(df)} barras ({df.index[0]} -> {df.index[-1]})")
        # La calidad de huecos se reporta como warning: ohlcv-1m omite minutos sin operaciones.
        report = quality.validate(df, tf, market_calendar=None)
        hard = [e for e in report.errors if "gap" not in e.lower() and "hueco" not in e.lower()]
        if hard:
            print(f"  Calidad FALLÓ: {'; '.join(hard)}")
            raise SystemExit(1)
        print(f"  {len(report.errors)} avisos de huecos, {len(report.warnings)} warnings")
        parquet_store.write_dataset(
            df, base=config["paths"]["raw"], symbol="6A", timeframe=tf, source=src.name,
            role=schema.ROLE_REAL, download_timestamp=download_ts,
        )
    print("Guardado en data/raw/6A/{M1,M5,H1}/. Ejecuta `make test` y revisa ADR-021.")


if __name__ == "__main__":
    main()
