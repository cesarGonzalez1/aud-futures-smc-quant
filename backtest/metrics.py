"""Costos y métricas de una hipótesis de trading (Fase 4, sección 6.3, ADR-007).

**Elección de herramienta (documentada):** NO se usa vectorbt aquí. vectorbt está
diseñado para vectorizar señales sobre una serie de precio continua (miles de
combinaciones de parámetros). La estrategia ADR-007 ya produce operaciones
DISCRETAS con entrada/stop/target resueltos por estructura de mercado (swing
opuesto), no por un cruce de señal simple. Sobre esa lista de operaciones, las
métricas (win rate, expectancy, max drawdown, Sharpe) son aritmética estándar
sobre los R-múltiplos — no reinventa un motor de backtest. vectorbt se mantiene
aprobado (ADR-002) y se usará en su terreno natural cuando haya una grilla de
parámetros que vectorizar. Consistente con la Filosofía Tecnológica: usar la
herramienta madura donde aporta, sin forzarla donde no encaja.

**Costos (obligatorios, sección 6.3):** medio spread real de M5 (bid/ask, columna
`spread` del dataset) en entrada y salida + slippage proporcional al ATR. Se
expresan como costo en precio y se convierten a fracción del riesgo (R).

**Tests múltiples:** UNA hipótesis predefinida → NO se aplica Deflated Sharpe
(ADR-007). Ajustar parámetros tras ver resultados activa el control de 6.2.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def apply_costs(
    trades: pd.DataFrame,
    *,
    half_spread: float,
    slippage_atr_frac: float = 0.05,
    atr: float = 0.0,
) -> pd.DataFrame:
    """Descuenta costos de cada operación y recalcula el R neto.

    Costo por lado = medio spread + slippage (fracción del ATR). Entrada y salida
    pagan costo, así que el costo total en precio ≈ 2·(half_spread + slippage). Se
    convierte a R dividiendo por el riesgo (|entry − stop|).

    Args:
        trades: DataFrame con columnas entry_price, stop, r_multiple.
        half_spread: medio spread en unidades de precio (ej. spread_medio/2).
        slippage_atr_frac: fracción del ATR como slippage por lado.
        atr: ATR de referencia en unidades de precio.

    Returns:
        Copia con columnas `cost_r` (costo en R) y `r_net` (R neto = r_multiple − cost_r).
    """
    out = trades.copy()
    if out.empty:
        out["cost_r"] = []
        out["r_net"] = []
        return out
    risk = (out["entry_price"] - out["stop"]).abs()
    cost_price = 2.0 * (half_spread + slippage_atr_frac * atr)
    out["cost_r"] = np.where(risk > 0, cost_price / risk, 0.0)
    out["r_net"] = out["r_multiple"] - out["cost_r"]
    return out


def _max_drawdown(equity: np.ndarray) -> float:
    """Máximo drawdown (en R) de una curva de equity acumulada."""
    if len(equity) == 0:
        return 0.0
    running_max = np.maximum.accumulate(equity)
    return float(np.max(running_max - equity))


def compute_metrics(trades: pd.DataFrame, *, r_col: str = "r_net") -> dict:
    """Métricas estándar sobre una lista de operaciones (usando el R indicado).

    Returns dict con: n_trades, win_rate, expectancy (media de R), r_total,
    max_drawdown_r, sharpe (media/desv de R, sin anualizar — es por-operación),
    avg_win, avg_loss.
    """
    if trades.empty or r_col not in trades.columns:
        return {"n_trades": 0, "win_rate": np.nan, "expectancy": np.nan,
                "r_total": 0.0, "max_drawdown_r": 0.0, "sharpe": np.nan,
                "avg_win": np.nan, "avg_loss": np.nan}
    r = trades[r_col].to_numpy()
    wins = r[r > 0]
    losses = r[r <= 0]
    std = r.std(ddof=1) if len(r) > 1 else np.nan
    return {
        "n_trades": int(len(r)),
        "win_rate": float((r > 0).mean()),
        "expectancy": float(r.mean()),
        "r_total": float(r.sum()),
        "max_drawdown_r": _max_drawdown(np.cumsum(r)),
        "sharpe": float(r.mean() / std) if std and not np.isnan(std) else np.nan,
        "avg_win": float(wins.mean()) if len(wins) else np.nan,
        "avg_loss": float(losses.mean()) if len(losses) else np.nan,
    }


def metrics_by_cohort(trades: pd.DataFrame, *, r_col: str = "r_net") -> pd.DataFrame:
    """Métricas por cohorte (6.4) + fila 'ALL'. Requiere columna `cohort`."""
    rows = []
    if not trades.empty and "cohort" in trades.columns:
        for cohort, g in trades.groupby("cohort"):
            rows.append({"cohort": cohort, **compute_metrics(g, r_col=r_col)})
    rows.append({"cohort": "ALL", **compute_metrics(trades, r_col=r_col)})
    return pd.DataFrame(rows)
