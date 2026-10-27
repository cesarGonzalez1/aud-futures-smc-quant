"""Módulo `backtest/` — costos y métricas de una hipótesis (Fase 4, sección 6.3).

metrics.py aplica costos (spread real + slippage por ATR) a las operaciones de
`strategy/` y calcula métricas estándar por cohorte. Ver ADR-007: es UNA hipótesis
predefinida → NO se aplica Deflated Sharpe; ajustar parámetros tras ver resultados
activa el control de tests múltiples (6.2).
"""
