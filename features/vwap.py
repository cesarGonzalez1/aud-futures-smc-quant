"""VWAP de sesión con bandas de desviación estándar (V12, SPEC_V12.md §1-2).

Replica el indicador VWAP por defecto de TradingView: ancla "Session", fuente
hlc3, ponderado por volumen, banda #1 = ±1.0 desviación estándar ponderada.

Ancla: apertura CME = 17:00 America/Chicago (zoneinfo, resuelve DST). El
volumen del proxy AUDUSD (Dukascopy) es CONTEO DE TICKS, no volumen de CME;
el VWAP resultante aproxima, no iguala, al de TradingView sobre 6A.

Point-in-time: en la barra t solo entran barras de la misma sesión con
timestamp <= t (acumulados). Se incluye la barra t porque su cierre ya es
conocido cuando se evalúa (los consumidores usan la barra del sweep ya cerrada).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema

__all__ = ["session_id", "add_session_vwap"]

ANCHOR_TZ = "America/Chicago"
ANCHOR_HOUR = 17


def session_id(index: pd.DatetimeIndex, *, tz: str = ANCHOR_TZ, anchor_hour: int = ANCHOR_HOUR) -> pd.Index:
    """Etiqueta de día de trading por barra: la fecha local de (hora local − anchor_hour).

    Una barra a las 17:00 locales ya pertenece a la sesión del día siguiente?  No:
    17:00 − 17h = 00:00 del MISMO día calendario local → la sesión se etiqueta con
    la fecha en que ABRE (la de las 17:00). Barras 00:00-16:55 del día D+1 caen en
    la sesión etiquetada D.
    """
    local = index.tz_convert(tz)
    shifted = local - pd.Timedelta(hours=anchor_hour)
    return pd.Index(shifted.normalize().tz_localize(None))


def add_session_vwap(df: pd.DataFrame, *, mult: float = 1.0) -> pd.DataFrame:
    """Añade `vwap`, `vwap_up`, `vwap_lo` (bandas ±`mult`·σ ponderada por volumen)."""
    out = df.copy()
    sid = session_id(out.index)
    src = ((out[schema.HIGH] + out[schema.LOW] + out[schema.CLOSE]) / 3.0).to_numpy()
    vol = out[schema.VOLUME].to_numpy(dtype=float) if schema.VOLUME in out.columns else np.ones(len(out))
    vol = np.where(vol > 0, vol, 1.0)  # barra sin ticks no anula el acumulado

    tmp = pd.DataFrame({"sid": sid, "pv": src * vol, "pv2": src * src * vol, "v": vol}, index=out.index)
    g = tmp.groupby("sid", sort=False)
    cv = g["v"].cumsum()
    vwap = g["pv"].cumsum() / cv
    var = g["pv2"].cumsum() / cv - vwap ** 2
    sd = np.sqrt(var.clip(lower=0.0))
    out["vwap"] = vwap.to_numpy()
    out["vwap_up"] = (vwap + mult * sd).to_numpy()
    out["vwap_lo"] = (vwap - mult * sd).to_numpy()
    return out
