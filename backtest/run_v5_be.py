"""Backtest V5 + gestión de breakeven móvil (ADR-012). EXPLORATORIO.

Misma señal/entrada/stop-inicial/target jerárquico que V5 (ADR-011) — cero
cambios ahí. Única diferencia: gestión dinámica del stop (breakeven a 0.4R a
favor, sin parciales — ver `strategy/trade_management.py` y
`backtest/run_v3_be.py` para la motivación completa).

Guarda `experiments/<fecha>_strat_liq_sweep_confluence_v5_breakeven/` sin tocar V5.

Ejecución:  python -m backtest.run_v5_be [--months N]
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import validity_label
from backtest.run_v5 import _prepare
from data import ingest
from strategy import liquidity_sweep_ifvg_v5 as v5
from strategy.trade_management import DEFAULT_BREAKEVEN_TRIGGER_R, apply_breakeven_management


def run(config: dict | None = None, months: int | None = None,
        breakeven_trigger_r: float = DEFAULT_BREAKEVEN_TRIGGER_R) -> dict:
    config = config or ingest.load_config()
    m5, h1, confluence, man, (window_start, window_end) = _prepare(config, months)

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    trades, confidences, sources = v5.generate_trades_v5(
        m5, h1, confluence, window_start=window_start, window_end=window_end,
    )
    trades_be = apply_breakeven_management(trades, m5, breakeven_trigger_r=breakeven_trigger_r)

    t5 = v5.trades_to_frame(trades_be, confidences, sources)
    t5 = metrics.apply_costs(t5, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)
    rescued = int((t5["outcome"] == "breakeven").sum()) if "outcome" in t5.columns else 0

    return {
        "trades": t5, "net": metrics.metrics_by_cohort(t5, r_col="r_net"),
        "n_total": len(t5), "validity": validity_label(len(t5)),
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": man.sha256, "role": man.role, "months": months,
        "breakeven_trigger_r": breakeven_trigger_r, "rescued": rescued,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_confluence_v5_breakeven"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: V5 + gestion breakeven movil (ADR-012), misma senal/entrada/target que V5\n"
        f"breakeven_trigger_r: {payload['breakeven_trigger_r']}\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"n_total: {payload['n_total']}\n"
        f"rescued_from_full_stop: {payload['rescued']}\n"
        f"window_months: {payload['months']}\n"
        f"validity_gate: \"{payload['validity']}\"\n"
        "deflated_sharpe: no aplica (una hipotesis predefinida, ADR-012)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n", encoding="utf-8")
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [f"# Backtest V5 + breakeven móvil (ADR-012) — {ts.date().isoformat()}", "",
             f"> {EXPLORATORY_NOTE}", "",
             f"## Gate (ADR-009): **{payload['n_total']} ops → {payload['validity']}**", "",
             f"Breakeven trigger: {payload['breakeven_trigger_r']}R  ·  "
             f"Operaciones rescatadas del stop completo: {payload['rescued']}", "",
             "## V5+BE NETO por cohorte", payload["net"].to_string(index=False)]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    months = None
    if "--months" in sys.argv:
        months = int(sys.argv[sys.argv.index("--months") + 1])
    config = ingest.load_config()
    payload = run(config, months=months)
    tag = f" (ventana {months} meses)" if months else " (5 años)"
    print(f"=== Backtest V5 + breakeven móvil (ADR-012){tag} — EXPLORATORIO ===")
    print(f"GATE: {payload['n_total']} operaciones → {payload['validity']}")
    print(f"Rescatadas del stop completo por breakeven: {payload['rescued']}")
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
