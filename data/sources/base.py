"""Contrato común de toda fuente de datos (ADR-001, ADR-005).

Cualquier fuente (Dukascopy, Stooq, ...) implementa `DataSource.fetch` y devuelve
un DataFrame en el esquema canónico (data/schema.py), ya normalizado a UTC. La
responsabilidad de traducir el formato propio de cada proveedor al canónico vive
dentro del adaptador, nunca aguas abajo. Esto mantiene los módulos desacoplados:
`analysis/` no sabe (ni debe saber) de qué proveedor vino el dato.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

import pandas as pd


class DataSource(ABC):
    """Fuente de datos de mercado normalizada al esquema del proyecto."""

    #: Identificador de la fuente, usado en el manifest (sección 10).
    name: str

    @abstractmethod
    def fetch(
        self,
        symbol: str,
        timeframe: str,
        start: datetime,
        end: datetime,
    ) -> pd.DataFrame:
        """Descarga datos y los devuelve en esquema canónico.

        Args:
            symbol: símbolo en la convención del proyecto (ej. "AUDUSD").
            timeframe: "H1" o "D1".
            start: inicio del rango (tz-aware UTC).
            end: fin del rango (tz-aware UTC).

        Returns:
            DataFrame indexado por `schema.TIMESTAMP` (UTC, ordenado), con al
            menos las columnas OHLC. Debe incluir `volume` y `spread` si la
            fuente los provee.

        Raises:
            NotImplementedError: en adaptadores aún no integrados.
            ValueError: si el símbolo/timeframe no lo soporta la fuente.
        """
        raise NotImplementedError
