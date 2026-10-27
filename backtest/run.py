"""Backtest de la hipótesis ADR-007 (Fase 4) — EXPLORATORIO.

Pipeline end-to-end:
  1. Carga M5/H1/D1 del proxy AUD/USD (data/raw).
  2. Prepara features necesarias: H1 (indicadores + estructura + sesiones + PDH/PDL
     + niveles Tokio); M5 (ATR + FVG/IFVG); bias diario desde D1.
  3. Genera operaciones (strategy/liquidity_sweep_ifvg, ADR-007).
  4. Aplica costos reales (medio spread M5 + slippage por ATR, sección 6.3).
  5. Métricas por cohorte (6.4) y guarda experimento autocontenido (sección 12).

ADVERTENCIAS (impresas y en el reporte):
  - Resultado EXPLORATORIO: primera prueba de una regla derivada del análisis, NO
    validación definitiva.
  - Estructura sobre PROXY spot AUD/USD, no el futuro real 6A (ADR-006).
  - UNA hipótesis predefinida → sin Deflated Sharpe; ajustar parámetros tras ver
    esto activa control de tests múltiples (6.2).

Ejecución:  python -m backtest.run
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backtest import metrics
from data import ingest
from data.storage import parquet_store
from data.storage.manifest import read_manifest
from features import indicators, levels, sessions, structure
from features.fvg import add_fvg_features
from strategy import liquidity_sweep_ifvg as strat

EXPLORATORY_NOTE = (
    "Resultado EXPLORATORIO (ADR-007): primera prueba de una regla derivada del "
    "análisis, NO una validación definitiva. Estructura sobre proxy spot AUD/USD, "
    "no el futuro real 6A (ADR-006). Una hipótesis predefinida => sin Deflated Sharpe; "
    "ajustar parámetros tras ver esto activa el control de tests múltiples (6.2)."
)


def _prepare(config: dict):
    raw = config["paths"]["raw"]
    sym = config["instruments"]["primary"]["symbol"]

    d1 = parquet_store.read_dataset(raw, sym, "D1")
    d1 = indicators.add_trend_momentum(d1)  # adx + ema_trend para el bias

    h1 = parquet_store.read_dataset(raw, sym, "H1")
    h1 = indicators.add_volatility(h1)
    h1 = structure.add_structure(h1)          # last_swing_high/low para el target
    h1 = sessions.add_sessions(h1, config["sessions"])
    h1 = levels.add_pdh_pdl(h1, d1)
    h1 = levels.add_tokyo_session_levels(h1)

    m5 = parquet_store.read_dataset(raw, sym, "M5")
    m5 = indicators.add_volatility(m5)        # atr para el filtro de tamaño de FVG
    m5 = add_fvg_features(m5, min_atr_frac=0.1)

    bias = strat.daily_bias_from_d1(d1)
    man = read_manifest(parquet_store.dataset_dir(raw, sym, "M5"))
    return h1, m5, bias, man


def run(config: dict | None = None) -> dict:
    config = config or ingest.load_config()
    h1, m5, bias, m5_manifest = _prepare(config)

    trades = strat.generate_trades(h1, m5, bias)
    tdf = strat.trades_to_frame(trades)

    # Costos con spread real de M5 y ATR de referencia (sección 6.3).
    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0
    tdf = metrics.apply_costs(tdf, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)

    gross = metrics.metrics_by_cohort(tdf, r_col="r_multiple")
    net = metrics.metrics_by_cohort(tdf, r_col="r_net")
    return {
        "trades": tdf, "gross": gross, "net": net,
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": m5_manifest.sha256, "role": m5_manifest.role,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_ifvg"
    exp.mkdir(parents=True, exist_ok=True)

    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio hipotesis ADR-007 (liquidity sweep + IFVG)\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"half_spread: {payload['half_spread']:.6f}\n"
        f"atr_ref: {payload['atr_ref']:.6f}\n"
        "deflated_sharpe: no aplica (una hipotesis predefinida, ADR-007)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n",
        encoding="utf-8",
    )
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [
        f"# Backtest exploratorio — liquidity sweep + IFVG (ADR-007) — {ts.date().isoformat()}",
        "", f"> {EXPLORATORY_NOTE}", "",
        f"Operaciones: {len(payload['trades'])}  ·  medio spread M5={payload['half_spread']:.6f}  ·  ATR ref={payload['atr_ref']:.6f}",
        "", "## Métricas NETAS (con costos) por cohorte", payload["net"].to_string(index=False),
        "", "## Métricas BRUTAS (sin costos) por cohorte", payload["gross"].to_string(index=False),
    ]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    config = ingest.load_config()
    payload = run(config)
    print("=== Backtest ADR-007 (EXPLORATORIO) ===")
    print(f"> {EXPLORATORY_NOTE}\n")
    print(f"Operaciones: {len(payload['trades'])}  medio_spread={payload['half_spread']:.6f}  atr_ref={payload['atr_ref']:.6f}\n")
    print("--- NETAS (con costos) ---")
    print(payload["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    exp = _write_experiment(payload, config)
    print(f"\nExperimento guardado en: {exp}")


if __name__ == "__main__":
    main()
