"""Ingesta puntual de un CSV exportado manualmente de TradingView (ADR-020).

No toca `make ingest` ni config/settings.yaml — es un comando aparte para no
arriesgar romper el pipeline automático con una fuente que depende de que el
usuario haya exportado archivos a mano primero.

Uso:
  python -m data.import_tradingview 6A H1
  python -m data.import_tradingview 6A M5 --start 2023-01-01 --end 2025-07-01
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone

from data import ingest, schema
from data.sources.tradingview_csv import TradingViewCSVSource
from data.storage import parquet_store
from data.validation import quality


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        raise SystemExit(1)
    symbol, timeframe = args[0], args[1]

    start = datetime(2015, 1, 1)
    end = datetime.now(timezone.utc)
    if "--start" in args:
        start = datetime.fromisoformat(args[args.index("--start") + 1])
    if "--end" in args:
        end = datetime.fromisoformat(args[args.index("--end") + 1])

    config = ingest.load_config()
    source = TradingViewCSVSource()

    print(f"Leyendo CSVs de {symbol} {timeframe} desde data/manual_imports/tradingview/ ...")
    df = source.fetch(symbol, timeframe, start, end)
    print(f"{len(df)} filas leídas ({df.index[0]} a {df.index[-1]}).")

    if df.empty:
        print("0 filas en el rango pedido — nada que ingerir.")
        return

    report = quality.validate(df, timeframe, market_calendar=None)
    if not report.is_valid:
        print(f"Calidad FALLÓ: {'; '.join(report.errors)}")
        raise SystemExit(1)

    download_ts = datetime.now(timezone.utc).isoformat()
    parquet_store.write_dataset(
        df, base=config["paths"]["raw"], symbol=symbol, timeframe=timeframe,
        source=source.name, role=schema.ROLE_REAL, download_timestamp=download_ts,
    )
    print(f"Guardado en data/raw/{symbol}/{timeframe}/ — {len(report.warnings)} warnings de calidad.")


if __name__ == "__main__":
    main()
