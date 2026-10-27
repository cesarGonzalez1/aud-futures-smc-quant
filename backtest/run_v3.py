"""Backtest V3 (ADR-009) — mecánica AMD en M5, comparado con V1/V2. EXPLORATORIO.

Toda la estructura (swing, sweep, order block, acumulación, equal highs/lows) y la
confirmación IFVG se calculan en M5; el bias del día sigue de D1 (contexto). Mismo
protocolo de costos (medio spread M5 + slippage ATR) y métricas por cohorte.

Gate de validez (ADR-009, declarado antes de ver el resultado):
  <100 ops  => "muestra insuficiente para cualquier conclusión"
  100-999   => "evidencia preliminar, no concluyente"
  >=1000    => base suficiente (con salvedades por cohorte)

Guarda `experiments/<fecha>_strat_liq_sweep_amd_m5_v3/` sin tocar V1/V2.

Ejecución:  python -m backtest.run_v3
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analysis import regime as regime_mod
from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from data import ingest
from data.storage import parquet_store
from data.storage.manifest import read_manifest
from features import indicators, levels, sessions, structure
from features.fvg import add_fvg_features
from strategy import liquidity_sweep_ifvg_v3 as v3


def validity_label(n: int) -> str:
    if n < 100:
        return "muestra insuficiente para cualquier conclusión (<100 ops, ADR-009)"
    if n < 1000:
        return "evidencia preliminar, no concluyente (100-999 ops, ADR-009)"
    return "base suficiente para lectura por cohorte (>=1000 ops, ADR-009)"


def _prepare_m5(config: dict):
    """Arma el frame M5 con toda la mecánica de estructura + niveles + IFVG."""
    raw = config["paths"]["raw"]
    sym = config["instruments"]["primary"]["symbol"]

    d1 = parquet_store.read_dataset(raw, sym, "D1")
    d1 = indicators.add_trend_momentum(d1)
    bias = v3.daily_bias_from_d1(d1)

    m5 = parquet_store.read_dataset(raw, sym, "M5")
    m5 = indicators.add_trend_momentum(m5)      # adx + ema_trend (régimen M5)
    m5 = indicators.add_volatility(m5)          # atr (filtros de tamaño)
    m5 = regime_mod.add_regime(m5)              # régimen M5 para la acumulación
    m5 = sessions.add_sessions(m5, config["sessions"])
    m5 = structure.add_structure(m5)            # swings + sweeps (M5)
    m5 = structure.add_order_blocks(m5)         # order blocks (M5)
    m5 = levels.add_pdh_pdl(m5, d1)
    m5 = levels.add_pwh_pwl(m5, d1)
    m5 = levels.add_tokyo_session_levels(m5)
    m5 = levels.add_equal_levels(m5)
    m5 = levels.add_accumulation_range(m5, window=config.get("v2", {}).get("acc_window", 6))
    m5 = add_fvg_features(m5, min_atr_frac=0.1)

    man = read_manifest(parquet_store.dataset_dir(raw, sym, "M5"))
    return m5, bias, man


def run(config: dict | None = None) -> dict:
    config = config or ingest.load_config()
    m5, bias, man = _prepare_m5(config)

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    trades = v3.generate_trades_v3(m5, bias)
    pois = getattr(v3.generate_trades_v3, "_last_pois", None)
    t3 = v3.trades_to_frame(trades, pois)
    t3 = metrics.apply_costs(t3, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)

    return {
        "trades": t3,
        "net": metrics.metrics_by_cohort(t3, r_col="r_net"),
        "n_total": len(t3),
        "validity": validity_label(len(t3)),
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": man.sha256, "role": man.role,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_amd_m5_v3"
    exp.mkdir(parents=True, exist_ok=True)

    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio V3 (mecanica AMD en M5, ADR-009)\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"n_total: {payload['n_total']}\n"
        f"validity_gate: \"{payload['validity']}\"\n"
        f"half_spread: {payload['half_spread']:.6f}\n"
        f"atr_ref: {payload['atr_ref']:.6f}\n"
        "deflated_sharpe: no aplica (una hipotesis predefinida, ADR-009)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n",
        encoding="utf-8",
    )
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [
        f"# Backtest V3 (mecánica AMD en M5, ADR-009) — {ts.date().isoformat()}", "",
        f"> {EXPLORATORY_NOTE}", "",
        f"## Gate de validez (ADR-009): **{payload['n_total']} operaciones → {payload['validity']}**", "",
        f"medio spread M5={payload['half_spread']:.6f}  ·  ATR ref={payload['atr_ref']:.6f}",
        "", "## V3 NETO por cohorte", payload["net"].to_string(index=False),
    ]
    if "poi" in payload["trades"].columns and not payload["trades"].empty:
        lines += ["", "## V3 — operaciones por POI barrido",
                  payload["trades"]["poi"].value_counts().to_string()]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    config = ingest.load_config()
    payload = run(config)
    print("=== Backtest V3 (mecánica AMD en M5, ADR-009) — EXPLORATORIO ===")
    print(f"> {EXPLORATORY_NOTE}\n")
    print(f"GATE DE VALIDEZ: {payload['n_total']} operaciones → {payload['validity']}\n")
    print("--- V3 NETO por cohorte ---")
    print(payload["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    exp = _write_experiment(payload, config)
    print(f"\nExperimento guardado en: {exp}")


if __name__ == "__main__":
    main()
