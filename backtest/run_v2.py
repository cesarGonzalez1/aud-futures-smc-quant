"""Backtest V2 (ADR-008) — AMD, comparado lado a lado con V1 (ADR-007). EXPLORATORIO.

Mismo protocolo de Fase 4 que V1 (costos reales: medio spread M5 + slippage ATR;
métricas por cohorte). Corre V1 y V2 sobre los mismos datos y reporta lado a lado.
Guarda experimento nuevo `experiments/<fecha>_strat_liq_sweep_amd_v2/` sin tocar el
de V1.

Nota de suficiencia (obligatoria): más POIs y una precondición extra cambian el
número de señales, pero MÁS señales no implica suficiencia estadística — el N por
cohorte se reporta explícito y, si es bajo como en V1, se declara igual.

Ejecución:  python -m backtest.run_v2
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from backtest import metrics
from backtest.run import EXPLORATORY_NOTE, _prepare
from data import ingest
from data.storage import parquet_store
from data.storage.manifest import read_manifest
from features import indicators, levels, structure
from strategy import liquidity_sweep_ifvg as v1
from strategy import liquidity_sweep_ifvg_v2 as v2
from analysis import regime as regime_mod


def _prepare_v2(config: dict):
    """Prepara H1/M5/bias de V1 y añade las columnas V2 (régimen, PWH/PWL, equal,
    acumulación, order blocks)."""
    h1, m5, bias, _ = _prepare(config)

    raw = config["paths"]["raw"]
    sym = config["instruments"]["primary"]["symbol"]
    d1 = parquet_store.read_dataset(raw, sym, "D1")

    # Régimen sobre H1 (para acumulación): necesita adx + ema_trend (no incluidos
    # en el _prepare de V1, que solo añade volatilidad).
    h1 = indicators.add_trend_momentum(h1)
    h1 = regime_mod.add_regime(h1)
    h1 = levels.add_pwh_pwl(h1, d1)
    h1 = levels.add_equal_levels(h1)
    h1 = levels.add_accumulation_range(h1, window=config.get("v2", {}).get("acc_window", 6))
    h1 = structure.add_order_blocks(h1)
    return h1, m5, bias


def run(config: dict | None = None) -> dict:
    config = config or ingest.load_config()
    h1, m5, bias = _prepare_v2(config)
    m5_manifest = read_manifest(parquet_store.dataset_dir(config["paths"]["raw"],
                                config["instruments"]["primary"]["symbol"], "M5"))

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    # V1 (idéntico a backtest.run) para comparación.
    t1 = v1.trades_to_frame(v1.generate_trades(h1, m5, bias))
    t1 = metrics.apply_costs(t1, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)

    # V2 (ADR-008).
    trades2 = v2.generate_trades_v2(h1, m5, bias)
    pois = getattr(v2.generate_trades_v2, "_last_pois", None)
    t2 = v2.trades_to_frame(trades2, pois)
    t2 = metrics.apply_costs(t2, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)

    return {
        "v1_trades": t1, "v2_trades": t2,
        "v1_net": metrics.metrics_by_cohort(t1, r_col="r_net"),
        "v2_net": metrics.metrics_by_cohort(t2, r_col="r_net"),
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": m5_manifest.sha256, "role": m5_manifest.role,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_amd_v2"
    exp.mkdir(parents=True, exist_ok=True)

    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio hipotesis V2 AMD (ADR-008), comparado con V1\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"half_spread: {payload['half_spread']:.6f}\n"
        f"atr_ref: {payload['atr_ref']:.6f}\n"
        "deflated_sharpe: no aplica (una hipotesis predefinida, ADR-008)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n",
        encoding="utf-8",
    )
    payload["v2_trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [
        f"# Backtest V2 (AMD, ADR-008) vs V1 — {ts.date().isoformat()}", "",
        f"> {EXPLORATORY_NOTE}", "",
        "> Suficiencia: MÁS señales no implica suficiencia estadística. El N por "
        "cohorte se reporta explícito; si es bajo, la lectura es igual de tentativa que V1.",
        "", f"medio spread M5={payload['half_spread']:.6f}  ·  ATR ref={payload['atr_ref']:.6f}",
        "", "## V1 (ADR-007) NETO por cohorte", payload["v1_net"].to_string(index=False),
        "", "## V2 (ADR-008) NETO por cohorte", payload["v2_net"].to_string(index=False),
    ]
    if "poi" in payload["v2_trades"].columns and not payload["v2_trades"].empty:
        lines += ["", "## V2 — operaciones por POI barrido",
                  payload["v2_trades"]["poi"].value_counts().to_string()]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    config = ingest.load_config()
    payload = run(config)
    fmt = lambda x: f"{x:.3g}"
    print("=== Backtest V2 (AMD, ADR-008) vs V1 — EXPLORATORIO ===")
    print(f"> {EXPLORATORY_NOTE}\n")
    print(f"V1 operaciones: {len(payload['v1_trades'])}  ·  V2 operaciones: {len(payload['v2_trades'])}\n")
    print("--- V1 NETO ---")
    print(payload["v1_net"].to_string(index=False, float_format=fmt))
    print("\n--- V2 NETO ---")
    print(payload["v2_net"].to_string(index=False, float_format=fmt))
    exp = _write_experiment(payload, config)
    print(f"\nExperimento guardado en: {exp}")


if __name__ == "__main__":
    main()
