"""Contexto cross-asset para AUD/USD (sección 7.5, ADR-005).

Incorpora al dataset primario (AUD/USD H1) tres series de contexto, todas vía
`merge_asof` backward para garantizar point-in-time (a cada barra en `t` se le
asigna el último valor disponible con timestamp <= t, nunca futuro):
  - XAU/USD (oro): términos de intercambio de Australia (Dukascopy, H1).
  - DXY (índice dólar): fortaleza del USD (Dukascopy nativo, D1 → constante intradía).
  - Diferencial de tasas RBA/Fed (tabla curada, escalón por decisión).

Limitación de resolución conocida (ADR-005): DXY es D1, así que su valor es
constante dentro del día en la serie H1. Es correcto point-in-time, pero la
resolución de ese contexto es diaria.
"""

from __future__ import annotations

import pandas as pd

from data import schema
from data.sources import rates_table


def _merge_series(primary: pd.DataFrame, series: pd.Series, out_col: str) -> pd.DataFrame:
    """merge_asof backward de una serie temporal sobre el índice del primario.

    Usa una clave derecha con nombre único (`_rkey`) para evitar colisiones cuando
    el primario y la serie comparten el nombre de índice (`timestamp`).
    """
    left = primary.sort_index()
    right = series.sort_index().rename(out_col)
    right.index = right.index.rename("_rkey")
    left_reset = left.reset_index()
    right_reset = right.reset_index()
    # merge_asof exige claves con el mismo dtype/resolución temporal; el crudo en
    # Parquet puede ser datetime64[ms] y una serie parseada de CSV datetime64[us].
    key = left.index.name
    right_reset["_rkey"] = right_reset["_rkey"].astype(left_reset[key].dtype)
    merged = pd.merge_asof(
        left_reset,
        right_reset,
        left_on=key,
        right_on="_rkey",
        direction="backward",
    ).set_index(key).drop(columns=["_rkey"])
    return merged


def add_cross_asset(
    primary: pd.DataFrame,
    *,
    xau: pd.DataFrame | None = None,
    dxy: pd.DataFrame | None = None,
    rates_csv: str | None = None,
) -> pd.DataFrame:
    """Añade columnas de contexto cross-asset point-in-time.

    Args:
        primary: dataset AUD/USD (índice UTC, nombre `timestamp`).
        xau: DataFrame XAU/USD (mismo timeframe) o None.
        dxy: DataFrame DXY (D1) o None.
        rates_csv: ruta a la tabla curada de tasas (ADR-005) o None.

    Returns:
        Copia de `primary` con `xau_close`, `dxy_close`, `rate_diff` según lo dado.
    """
    out = primary.copy()
    if xau is not None:
        out = _merge_series(out, xau[schema.CLOSE], "xau_close")
    if dxy is not None:
        out = _merge_series(out, dxy[schema.CLOSE], "dxy_close")
    if rates_csv is not None:
        rates = rates_table.load(rates_csv).set_index("fecha_efectiva")
        out = _merge_series(out, rates["diferencial"], "rate_diff")
    return out
