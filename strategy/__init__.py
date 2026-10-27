"""Módulo `strategy/` — reglas de trading formalizadas (Fase 4).

liquidity_sweep_ifvg.py implementa la hipótesis ADR-007 (bias D1 → sweep H1 →
confirmación IFVG M5 → entrada/stop/target). Produce una lista de operaciones
simuladas; el backtest con costos y métricas por cohorte va en `backtest/`.
Acoplamiento solo por disco (lee Parquet de data/), como el resto de módulos.
"""
