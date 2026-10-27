"""Hipótesis V10 (ADR-016) — V9 (MSS-only) + SMT (6A vs 6N) como gate diario.

SMT solo existe a nivel D1 (limitación de la fuente Yahoo, ver `features/smt.py`
y ADR-016) — no es un evento M5 como MSS/CISD, así que no compite por el mismo
timestamp de confirmación dentro de la ventana de entrada. Se integra como un
gate adicional a nivel de DÍA, igual que el bias de confluencia (`features.bias`,
también D1/H4): de las operaciones que V9 ya genera (MSS-only), se exige además
que el día de entrada tenga divergencia SMT en la MISMA dirección del trade
(`smt_bear` para cortos, `smt_bull` para largos).

No cambia la generación de V9 en absoluto — es un filtro posterior sobre las
mismas operaciones, aplicado con la misma disciplina que cualquier filtro de
capa 3 (contexto): reduce la muestra, nunca la infla ni cambia entrada/stop/target.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["filter_trades_by_smt"]


def filter_trades_by_smt(trades: pd.DataFrame, smt_daily: pd.DataFrame) -> pd.DataFrame:
    """Conserva solo las operaciones cuyo día de entrada tiene divergencia SMT
    (`smt_bear`/`smt_bull`, `features.smt.add_smt_divergence`) alineada con el
    lado del trade.

    Args:
        trades: DataFrame de operaciones (columnas `entry_time`, `side`), p.ej.
            la salida de `strategy.liquidity_sweep_ifvg_v7.trades_to_frame`.
        smt_daily: salida de `features.smt.add_smt_divergence` (índice D1, UTC).

    Returns:
        Subconjunto de `trades` (mismas columnas) que cumple el gate SMT. Si un
        día de entrada no existe en `smt_daily`, la operación se descarta (no se
        asume alineación sin evidencia).
    """
    if trades.empty:
        return trades

    day = pd.to_datetime(trades["entry_time"]).dt.tz_convert("UTC").dt.normalize()
    smt = smt_daily[["smt_bear", "smt_bull"]].sort_index()
    aligned = smt.reindex(day.to_numpy())
    required = np.where(
        trades["side"].to_numpy() == "short",
        aligned["smt_bear"].to_numpy(),
        aligned["smt_bull"].to_numpy(),
    )
    mask = pd.Series(required, index=trades.index).fillna(False).astype(bool)
    return trades[mask].reset_index(drop=True)
