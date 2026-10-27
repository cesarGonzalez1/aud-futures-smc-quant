"""Pipeline de ingesta Fase 1 (sección 14).

Orquesta, para cada instrumento configurado en config/settings.yaml:
    fetch (adaptador de fuente) -> validate (calidad) -> write (parquet + manifest).

Ejecución manual (ADR-000, sin orquestador):  `python -m data.ingest`

Determinismo: el sello de tiempo de descarga se lee UNA sola vez al inicio y se
propaga a todos los manifests, para que una corrida sea trazable a un instante.
Un dataset que falla la validación de calidad detiene su rama y se reporta; no se
escribe dato inválido (regla: un dato no válido no es "raw validado").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

from data import schema
from data.sources.base import DataSource
from data.sources.dukascopy import DukascopySource
from data.sources.stooq import StooqSource
from data.sources.tradingview_csv import TradingViewCSVSource
from data.sources.yahoo_futures import YahooFuturesSource
from data.storage import parquet_store
from data.validation import quality

CONFIG_PATH = "config/settings.yaml"

#: Registro de adaptadores disponibles por nombre de fuente.
SOURCES: dict[str, DataSource] = {
    "dukascopy": DukascopySource(),
    "stooq": StooqSource(),
    "yahoo_futures": YahooFuturesSource(),
    "tradingview_csv": TradingViewCSVSource(),  # ADR-020, requiere exportación manual del usuario
}


@dataclass
class IngestResult:
    """Resultado de ingerir un (symbol, timeframe)."""

    symbol: str
    timeframe: str
    ok: bool
    rows: int
    message: str


def load_config(path: str | Path = CONFIG_PATH) -> dict:
    """Carga la configuración YAML del proyecto."""
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))


def _iter_targets(config: dict):
    """Genera dicts de target desde la config: source, symbol, timeframe, role,
    market_calendar. Cubre el activo real (ADR-006), el proxy primario y los
    cross-asset. `role` y `market_calendar` tienen defaults por si faltan."""
    instr = config["instruments"]
    entries = []
    if "real_asset" in instr:
        entries.append(instr["real_asset"])
    entries.append(instr["primary"])
    entries.extend(instr.get("cross_asset", []))

    for entry in entries:
        for tf in entry["timeframes"]:
            yield {
                "source": entry["source"],
                "symbol": entry["symbol"],
                "timeframe": tf,
                "role": entry.get("role", schema.ROLE_CONTEXT),
                "market_calendar": entry.get("market_calendar"),
            }


def ingest_one(
    source: DataSource,
    symbol: str,
    timeframe: str,
    start: datetime,
    end: datetime,
    *,
    raw_base: str,
    download_ts: str,
    quality_cfg: dict,
    role: str = schema.ROLE_CONTEXT,
    market_calendar: str | None = None,
) -> IngestResult:
    """Ingesta de un único (symbol, timeframe): fetch -> validate -> write.

    Devuelve IngestResult en vez de lanzar, para que una falla de un instrumento
    no aborte la corrida completa; el resumen final lista qué pasó con cada uno.

    `role` (ADR-006) se graba en el manifest. `market_calendar` selecciona el
    calendario de mercado para clasificar huecos (ej. CME_FX para 6A).
    """
    try:
        df = source.fetch(symbol, timeframe, start, end)
    except NotImplementedError as exc:
        return IngestResult(symbol, timeframe, False, 0, f"pendiente: {exc}")
    except Exception as exc:  # noqa: BLE001 - se reporta, no se oculta
        return IngestResult(symbol, timeframe, False, 0, f"fetch falló: {exc}")

    if df.empty:
        # 0 filas es un resultado legítimo (p.ej. rango pedido fuera de la
        # ventana que Yahoo intradía puede servir hoy — ver avisos de
        # yahoo_futures) — NO es un fallo de calidad ni hay nada que escribir.
        # Validar/escribir un DataFrame vacío no tiene sentido y rompe
        # `write_dataset` (asume >=1 fila para nombrar el archivo).
        return IngestResult(symbol, timeframe, True, 0, "0 filas (rango fuera de lo disponible, no es un error)")

    report = quality.validate(
        df,
        timeframe,
        zscore_threshold=quality_cfg.get("price_outlier_zscore", 8.0),
        weekend_gap_allowed=quality_cfg.get("weekend_gap_allowed", True),
        error_gap_days=quality_cfg.get("error_gap_days", 7.0),
        market_calendar=market_calendar,
    )
    if not report.is_valid:
        return IngestResult(
            symbol, timeframe, False, len(df),
            "calidad FALLÓ: " + "; ".join(report.errors),
        )

    parquet_store.write_dataset(
        df,
        base=raw_base,
        source=source.name,
        symbol=symbol,
        timeframe=timeframe,
        download_timestamp=download_ts,
        role=role,
    )
    warn = f" ({len(report.warnings)} warnings)" if report.warnings else ""
    return IngestResult(symbol, timeframe, True, len(df), f"OK [{role}]{warn}")


def run(config_path: str | Path = CONFIG_PATH) -> list[IngestResult]:
    """Corre el pipeline completo de ingesta Fase 1.

    Returns:
        Lista de IngestResult, uno por (symbol, timeframe) intentado.
    """
    config = load_config(config_path)
    hist = config["history"]
    start = pd.Timestamp(hist["start"], tz="UTC").to_pydatetime()
    end = pd.Timestamp(hist["end"], tz="UTC").to_pydatetime()
    raw_base = config["paths"]["raw"]
    quality_cfg = config.get("quality", {})
    download_ts = datetime.now(timezone.utc).isoformat()

    results: list[IngestResult] = []
    for tgt in _iter_targets(config):
        source = SOURCES.get(tgt["source"])
        if source is None:
            results.append(
                IngestResult(tgt["symbol"], tgt["timeframe"], False, 0,
                             f"fuente desconocida: {tgt['source']}")
            )
            continue
        results.append(
            ingest_one(
                source, tgt["symbol"], tgt["timeframe"], start, end,
                raw_base=raw_base, download_ts=download_ts, quality_cfg=quality_cfg,
                role=tgt["role"], market_calendar=tgt["market_calendar"],
            )
        )
    return results


def main() -> None:
    """Punto de entrada CLI: corre la ingesta e imprime un resumen legible."""
    results = run()
    print("\n=== Resumen de ingesta Fase 1 ===")
    for r in results:
        status = "✓" if r.ok else "✗"
        print(f"  {status} {r.symbol:8} {r.timeframe:3}  {r.rows:>7} filas  {r.message}")


if __name__ == "__main__":
    main()
