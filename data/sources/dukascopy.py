"""Adaptador Dukascopy — fuente primaria de precio (ADR-001).

Usa la librería `dukascopy-python` (PyPI), NO `duka` (ver ADR-001 para la razón).
Dukascopy publica histórico gratuito de forex/metales/índices con >5 años de
profundidad y con lados BID y ASK por separado.

Spread histórico (sección 6.3): Dukascopy no entrega una columna de spread; se
obtiene pidiendo los lados BID y ASK por separado y calculando
`spread = ask.close - bid.close` por barra. Pedir un solo lado NO permite modelar
costos de transacción, por eso el adaptador siempre pide ambos.

Salida en esquema canónico (data/schema.py):
    open, high, low, close, volume  -> del lado BID (convención de cotización)
    spread                          -> ask.close - bid.close
Índice `timestamp` en UTC (la librería ya lo entrega así).
"""

from __future__ import annotations

from datetime import datetime

import pandas as pd

import dukascopy_python as dk
from dukascopy_python import instruments as dk_instruments

from data import schema
from data.sources.base import DataSource

#: Símbolo del proyecto -> constante de instrumento de dukascopy-python.
SYMBOL_MAP: dict[str, str] = {
    "AUDUSD": dk_instruments.INSTRUMENT_FX_MAJORS_AUD_USD,
    "XAUUSD": dk_instruments.INSTRUMENT_FX_METALS_XAU_USD,
    # Índice dólar nativo de Dukascopy (ver ADR-005: alternativa a Stooq para DXY).
    "DXY": dk_instruments.INSTRUMENT_IDX_AMERICA_DOLLAR_IDX_USD,
}

#: Timeframe del proyecto -> constante de intervalo de dukascopy-python.
INTERVAL_MAP: dict[str, str] = {
    "M5": dk.INTERVAL_MIN_5,
    "H1": dk.INTERVAL_HOUR_1,
    "D1": dk.INTERVAL_DAY_1,
}


class DukascopySource(DataSource):
    """Fuente de precio Dukascopy (AUD/USD, XAU/USD, DXY) con spread BID/ASK."""

    name = "dukascopy"

    def fetch(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        if symbol not in SYMBOL_MAP:
            raise ValueError(
                f"Símbolo {symbol!r} no mapeado para Dukascopy. "
                f"Soportados: {sorted(SYMBOL_MAP)}"
            )
        if timeframe not in INTERVAL_MAP:
            raise ValueError(
                f"Timeframe {timeframe!r} no soportado. "
                f"Soportados: {sorted(INTERVAL_MAP)}"
            )

        instrument = SYMBOL_MAP[symbol]
        interval = INTERVAL_MAP[timeframe]

        bid = dk.fetch(instrument, interval, dk.OFFER_SIDE_BID, start, end)
        ask = dk.fetch(instrument, interval, dk.OFFER_SIDE_ASK, start, end)

        if bid.empty:
            return self._empty_frame()

        # OHLCV desde BID (convención de cotización para entradas/salidas en forex).
        out = bid[[schema.OPEN, schema.HIGH, schema.LOW, schema.CLOSE, schema.VOLUME]].copy()

        # Spread = ask.close - bid.close, alineado por timestamp. Barras sin lado
        # ASK correspondiente quedan con spread NaN (se reporta en validación).
        ask_close = ask[schema.CLOSE].reindex(out.index)
        out[schema.SPREAD] = ask_close - out[schema.CLOSE]

        out.index.name = schema.TIMESTAMP
        out = out.sort_index()
        return out

    @staticmethod
    def _empty_frame() -> pd.DataFrame:
        """DataFrame vacío con el esquema canónico (rango sin datos, ej. feriado)."""
        cols = [schema.OPEN, schema.HIGH, schema.LOW, schema.CLOSE, schema.VOLUME, schema.SPREAD]
        idx = pd.DatetimeIndex([], tz="UTC", name=schema.TIMESTAMP)
        return pd.DataFrame(columns=cols, index=idx)
