"""Backtest V6 (ADR-014): señal simple de V1 + stop de swing H1. EXPLORATORIO.

Combina lo mejor de dos hallazgos previos: V1 tuvo la mejor expectativa de las
5 hipótesis de entrada (−0.27R), y ADR-010 mostró que ensanchar el stop reduce el
peso de los costos (aunque por sí solo no bastó en V3→V4). Aquí se aplica el
mismo cambio de stop, pero sobre la señal más simple (V1) en vez de la más
compleja (V3), para ver si el punto de partida importa.

Guarda `experiments/<fecha>_strat_liq_sweep_ifvg_v6/` sin tocar V1.

Ejecución:  python -m backtest.run_v6
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from data import ingest
from data.storage import parquet_store
from data.storage.manifest import read_manifest
from features import indicators, levels, sessions, structure
from features.fvg import add_fvg_features
from strategy import liquidity_sweep_ifvg as v1
from strategy import liquidity_sweep_ifvg_v6 as v6


def validity_label(n: int) -> str:
    if n < 100:
        return "muestra insuficiente para cualquier conclusión (<100 ops, ADR-009)"
    if n < 1000:
        return "evidencia preliminar, no concluyente (100-999 ops, ADR-009)"
    return "evidencia suficiente para lectura más confiable (≥1000 ops, ADR-009)"


def _prepare(config: dict):
    raw = config["paths"]["raw"]
    sym = config["instruments"]["primary"]["symbol"]

    d1 = parquet_store.read_dataset(raw, sym, "D1")
    d1 = indicators.add_trend_momentum(d1)

    h1 = parquet_store.read_dataset(raw, sym, "H1")
    h1 = indicators.add_volatility(h1)
    h1 = structure.add_structure(h1)    # last_swing_high/low -> ahora TAMBIÉN el stop (ADR-014)
    h1 = sessions.add_sessions(h1, config["sessions"])
    h1 = levels.add_pdh_pdl(h1, d1)
    h1 = levels.add_tokyo_session_levels(h1)

    m5 = parquet_store.read_dataset(raw, sym, "M5")
    m5 = indicators.add_volatility(m5)
    m5 = structure.add_structure(m5)    # necesario para el trailing (ADR-013) sobre esta base
    m5 = add_fvg_features(m5, min_atr_frac=0.1)

    bias = v1.daily_bias_from_d1(d1)
    man = read_manifest(parquet_store.dataset_dir(raw, sym, "M5"))
    return h1, m5, bias, man


def run(config: dict | None = None) -> dict:
    config = config or ingest.load_config()
    h1, m5, bias, man = _prepare(config)

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    trades = v6.generate_trades_v6(h1, m5, bias)
    tdf = v6.trades_to_frame(trades)
    tdf = metrics.apply_costs(tdf, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)

    return {
        "trades": tdf, "net": metrics.metrics_by_cohort(tdf, r_col="r_net"),
        "n_total": len(tdf), "validity": validity_label(len(tdf)),
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": man.sha256, "role": man.role,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_ifvg_v6"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: V6 (ADR-014) - senal simple de V1 + stop de swing H1 (ADR-010)\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"n_total: {payload['n_total']}\n"
        f"validity_gate: \"{payload['validity']}\"\n"
        f"half_spread: {payload['half_spread']:.6f}\n"
        f"atr_ref: {payload['atr_ref']:.6f}\n"
        "deflated_sharpe: no aplica (una hipotesis predefinida, ADR-014)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n", encoding="utf-8")
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [f"# Backtest V6 — señal V1 + stop swing H1 (ADR-014) — {ts.date().isoformat()}", "",
             f"> {EXPLORATORY_NOTE}", "",
             f"## Gate (ADR-009): **{payload['n_total']} ops → {payload['validity']}**", "",
             "## V6 NETO por cohorte", payload["net"].to_string(index=False)]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    config = ingest.load_config()
    payload = run(config)
    print("=== Backtest V6 — señal V1 + stop swing H1 (ADR-014) — EXPLORATORIO ===")
    print(f"GATE: {payload['n_total']} operaciones → {payload['validity']}")
    print(payload["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
