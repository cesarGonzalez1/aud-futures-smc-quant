"""Indicadores clásicos de tendencia, momentum y volatilidad (sección 7.1-7.2).

Usa la librería `ta` (ADR-000). Todos los indicadores usan ventanas móviles
hacia atrás (rolling), por lo que son point-in-time por construcción: el valor en
`t` solo depende de datos hasta `t`. Cada columna añadida documenta su ventana.
"""

from __future__ import annotations

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import ADXIndicator, EMAIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands

from data import schema


def add_trend_momentum(
    df: pd.DataFrame,
    *,
    ema_fast: int = 12,
    ema_slow: int = 26,
    ema_trend: int = 50,
    rsi_window: int = 14,
    adx_window: int = 14,
) -> pd.DataFrame:
    """Añade tendencia y momentum: EMA(fast/slow/trend), MACD, RSI, ADX.

    `ema_trend` (default 50) es el que usa ADR-003 para el régimen de tendencia
    junto con ADX. Todos los parámetros son defaults configurables (sección 16).
    """
    out = df.copy()
    close, high, low = out[schema.CLOSE], out[schema.HIGH], out[schema.LOW]

    out["ema_fast"] = EMAIndicator(close, ema_fast).ema_indicator()
    out["ema_slow"] = EMAIndicator(close, ema_slow).ema_indicator()
    out["ema_trend"] = EMAIndicator(close, ema_trend).ema_indicator()

    macd = MACD(close, window_slow=ema_slow, window_fast=ema_fast)
    out["macd"] = macd.macd()
    out["macd_signal"] = macd.macd_signal()
    out["macd_hist"] = macd.macd_diff()

    out["rsi"] = RSIIndicator(close, rsi_window).rsi()

    adx = ADXIndicator(high, low, close, adx_window)
    out["adx"] = adx.adx()
    out["adx_pos"] = adx.adx_pos()
    out["adx_neg"] = adx.adx_neg()
    return out


def add_volatility(
    df: pd.DataFrame,
    *,
    atr_window: int = 14,
    bb_window: int = 20,
    bb_dev: float = 2.0,
) -> pd.DataFrame:
    """Añade volatilidad: ATR y Bollinger Bands (alto/bajo/ancho).

    ATR(14) alimenta el régimen de volatilidad de ADR-003 (percentil móvil).
    """
    out = df.copy()
    close, high, low = out[schema.CLOSE], out[schema.HIGH], out[schema.LOW]

    out["atr"] = AverageTrueRange(high, low, close, atr_window).average_true_range()

    bb = BollingerBands(close, bb_window, bb_dev)
    out["bb_high"] = bb.bollinger_hband()
    out["bb_low"] = bb.bollinger_lband()
    out["bb_width"] = bb.bollinger_wband()
    return out
