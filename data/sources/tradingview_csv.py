"""Adaptador para CSVs exportados MANUALMENTE de TradingView (ADR-020).

**Por qué manual, no automatizado:** TradingView no tiene API pública oficial
para descargas automatizadas (confirmado por investigación, enero-mayo 2026:
ni Pineify ni BacktestBase, ambas guías actuales, mencionan una). La
exportación ("Download chart data...") es una función manual del navegador,
disponible solo en planes Plus/Premium (o su prueba gratuita de 30 días) — el
plan gratuito no incluye exportación nativa. Existen extensiones de Chrome que
scrapean el DOM, pero son menos confiables y la mayoría limitan a 25 filas en
su versión gratuita — no valen la pena frente a la exportación nativa durante
una prueba gratuita de Plus/Premium.

**Cómo exportar (con tu prueba gratuita Plus/Premium):**
    1. Abre el gráfico de 6A (o el símbolo del futuro CME que uses en
       TradingView) en la temporalidad que quieras (M1/M5/H1/H4/D1).
    2. Desplázate hacia atrás (scroll/zoom del eje X) para cargar TODA la
       historia que quieras exportar — la exportación SOLO incluye las velas
       ya cargadas en pantalla, no descarga automáticamente más atrás.
    3. Menú hamburguesa (☰, arriba) -> "Download chart data..." (o
       "Export chart data...") -> formato de fecha "ISO time" (más fácil de
       parsear) -> Exportar.
    4. Límite por exportación: ~10,000 velas (Plus) o ~20,000 (Premium). Si
       necesitas más historia de la que cabe en una exportación, repite el
       proceso desplazándote más atrás y exporta varios archivos — este
       adaptador los concatena automáticamente (ver `_read_all_chunks`).
    5. Guarda los CSV en `data/manual_imports/tradingview/` con el nombre
       `{symbol}_{timeframe}.csv` (o `{symbol}_{timeframe}__2.csv`,
       `__3.csv`, etc. si son varios archivos del mismo símbolo/temporalidad
       — cualquier sufijo tras `__` sirve, se concatenan y deduplican).

**Realismo sobre cuánto esfuerzo manual toma cada temporalidad** (1 año de
sesión ~21h/semana en FX/futuros 24/5): D1 y H4 -> 1 sola exportación cubre
años. H1 -> 1-2 exportaciones para ~2-3 años. M5 -> ~5-6 exportaciones POR AÑO
(demasiadas velas para una sola exportación). M1 -> impráctico para más de
unas semanas de historia por este método manual — si necesitas M1 profundo,
Interactive Brokers (ADR-018, aún no implementado) sigue siendo mejor camino.

**Legal/ToS (no es asesoría legal, solo lo que dicen las fuentes consultadas):**
uso personal para backtesting propio es la práctica aceptada; redistribuir
los datos de TradingView comercialmente no lo es. Este proyecto es uso
personal.
"""

from __future__ import annotations

import glob
import os
from datetime import datetime

import pandas as pd

from data import schema
from data.sources.base import DataSource

DEFAULT_IMPORT_DIR = "data/manual_imports/tradingview"

_COLUMN_ALIASES = {
    "open": schema.OPEN, "high": schema.HIGH, "low": schema.LOW, "close": schema.CLOSE,
    "volume": schema.VOLUME,
}


def _parse_time_column(series: pd.Series) -> pd.DatetimeIndex:
    """TradingView exporta el tiempo como ISO ("2020-07-21T06:00:00Z") o
    Unix (segundos, "1595311200") según lo elegido al exportar — se detectan
    ambos formatos automáticamente."""
    if pd.api.types.is_numeric_dtype(series):
        return pd.to_datetime(series, unit="s", utc=True)
    parsed = pd.to_datetime(series, utc=True, errors="coerce")
    if parsed.isna().any():
        raise ValueError(
            "No pude parsear la columna de tiempo del CSV de TradingView — "
            "exporta con formato 'ISO time' o 'UNIX timestamp' (no otro)."
        )
    return parsed


def _read_one(path: str) -> pd.DataFrame:
    raw = pd.read_csv(path)
    raw.columns = [str(c).strip().lower() for c in raw.columns]
    time_col = raw.columns[0]  # TradingView siempre pone el tiempo en la primera columna
    idx = _parse_time_column(raw[time_col])

    out = pd.DataFrame(index=idx)
    for src_col, canonical in _COLUMN_ALIASES.items():
        if src_col in raw.columns:
            out[canonical] = raw[src_col].to_numpy()
    missing = {schema.OPEN, schema.HIGH, schema.LOW, schema.CLOSE} - set(out.columns)
    if missing:
        raise ValueError(f"El CSV {path!r} no tiene columnas {missing} — ¿exportaste OHLC?")
    out.index.name = schema.TIMESTAMP
    return out.sort_index()


class TradingViewCSVSource(DataSource):
    """Lee CSVs exportados a mano desde TradingView (ADR-020). No descarga
    nada — el usuario exporta manualmente y los coloca en `import_dir`.
    """

    name = "tradingview_csv"

    def __init__(self, import_dir: str = DEFAULT_IMPORT_DIR):
        self.import_dir = import_dir

    def fetch(self, symbol: str, timeframe: str, start: datetime, end: datetime) -> pd.DataFrame:
        pattern = os.path.join(self.import_dir, f"{symbol}_{timeframe}*.csv")
        paths = sorted(glob.glob(pattern))
        if not paths:
            raise FileNotFoundError(
                f"No encontré CSVs en {pattern!r}. Exporta desde TradingView y guárdalos ahí "
                f"(ver docstring de este módulo para el paso a paso)."
            )

        frames = [_read_one(p) for p in paths]
        df = pd.concat(frames)
        df = df[~df.index.duplicated(keep="first")].sort_index()

        start_ts, end_ts = pd.Timestamp(start), pd.Timestamp(end)
        start_ts = start_ts.tz_localize("UTC") if start_ts.tz is None else start_ts.tz_convert("UTC")
        end_ts = end_ts.tz_localize("UTC") if end_ts.tz is None else end_ts.tz_convert("UTC")
        return df[(df.index >= start_ts) & (df.index <= end_ts)]
