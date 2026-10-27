"""Backtest V6 + trailing stop por estructura (ADR-013 aplicado sobre ADR-014).
EXPLORATORIO. Esta es la combinación completa pedida: señal simple de V1 + stop
ancho de swing H1 (V4-style) + gestión de trailing por estructura (regla real
del usuario).

Guarda `experiments/<fecha>_strat_liq_sweep_ifvg_v6_trailing/` sin tocar V6 base
ni ninguna otra versión.

Ejecución:  python -m backtest.run_v6_trail
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from backtest.run_v6 import _prepare, validity_label
from data import ingest
from strategy import liquidity_sweep_ifvg_v6 as v6
from strategy.trade_management import apply_structure_trailing_stop


def run(config: dict | None = None, lag_swings: int = 1) -> dict:
    config = config or ingest.load_config()
    h1, m5, bias, man = _prepare(config)

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    trades = v6.generate_trades_v6(h1, m5, bias)
    trades_tr = apply_structure_trailing_stop(trades, m5, lag_swings=lag_swings)

    tdf = v6.trades_to_frame(trades_tr)
    tdf = metrics.apply_costs(tdf, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)
    rescued = int((tdf["outcome"] == "trailing_stop").sum()) if "outcome" in tdf.columns else 0

    return {
        "trades": tdf, "net": metrics.metrics_by_cohort(tdf, r_col="r_net"),
        "n_total": len(tdf), "validity": validity_label(len(tdf)),
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": man.sha256, "role": man.role,
        "lag_swings": lag_swings, "rescued": rescued,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_ifvg_v6_trailing"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: V6 + trailing por estructura (ADR-013 sobre ADR-014)\n"
        f"lag_swings: {payload['lag_swings']}\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"n_total: {payload['n_total']}\n"
        f"exits_via_trailing_stop: {payload['rescued']}\n"
        f"validity_gate: \"{payload['validity']}\"\n"
        "deflated_sharpe: no aplica (una hipotesis predefinida, ADR-014)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n", encoding="utf-8")
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [f"# Backtest V6 + trailing por estructura (ADR-014+013) — {ts.date().isoformat()}", "",
             f"> {EXPLORATORY_NOTE}", "",
             f"## Gate (ADR-009): **{payload['n_total']} ops → {payload['validity']}**", "",
             f"lag_swings={payload['lag_swings']}  ·  Salidas vía trailing: {payload['rescued']}",
             "", "## V6+Trailing NETO por cohorte", payload["net"].to_string(index=False)]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    config = ingest.load_config()
    payload = run(config)
    print("=== Backtest V6 + trailing por estructura (ADR-014+013) — EXPLORATORIO ===")
    print(f"GATE: {payload['n_total']} operaciones → {payload['validity']}")
    print(f"Salidas vía trailing: {payload['rescued']}")
    print(payload["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
