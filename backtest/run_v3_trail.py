"""Backtest V3 + trailing stop por estructura (ADR-013). EXPLORATORIO.

Reemplaza el breakeven simple de ADR-012 (verificado negativo: precio exacto de
entrada sin colchón corta ganadoras reales en la retracción normal, ver
CLAUDE.md) por la regla REAL del usuario: el stop avanza al swing confirmado que
queda "un impulso atrás" del más reciente (nunca al más nuevo — deja colchón),
solo a favor. Misma señal/entrada/stop-inicial/target que V3, cero cambios ahí.

Guarda `experiments/<fecha>_strat_liq_sweep_amd_m5_v3_trailing/` sin tocar V3 ni
V3+breakeven (ADR-012, conservado como conocimiento).

Ejecución:  python -m backtest.run_v3_trail
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import _prepare_m5, validity_label
from data import ingest
from strategy import liquidity_sweep_ifvg_v3 as v3
from strategy.trade_management import apply_structure_trailing_stop


def run(config: dict | None = None, lag_swings: int = 1) -> dict:
    config = config or ingest.load_config()
    m5, bias, man = _prepare_m5(config)

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    trades = v3.generate_trades_v3(m5, bias)
    pois = getattr(v3.generate_trades_v3, "_last_pois", None)
    trades_tr = apply_structure_trailing_stop(trades, m5, lag_swings=lag_swings)

    t3 = v3.trades_to_frame(trades_tr, pois)
    t3 = metrics.apply_costs(t3, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)
    rescued = int((t3["outcome"] == "trailing_stop").sum()) if "outcome" in t3.columns else 0

    return {
        "trades": t3, "net": metrics.metrics_by_cohort(t3, r_col="r_net"),
        "n_total": len(t3), "validity": validity_label(len(t3)),
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": man.sha256, "role": man.role,
        "lag_swings": lag_swings, "rescued": rescued,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_amd_m5_v3_trailing"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: V3 + trailing stop por estructura (ADR-013), misma senal/entrada/target que V3\n"
        f"lag_swings: {payload['lag_swings']}\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"n_total: {payload['n_total']}\n"
        f"exits_via_trailing_stop: {payload['rescued']}\n"
        f"validity_gate: \"{payload['validity']}\"\n"
        "deflated_sharpe: no aplica (una hipotesis predefinida, ADR-013)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n", encoding="utf-8")
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [f"# Backtest V3 + trailing stop por estructura (ADR-013) — {ts.date().isoformat()}", "",
             f"> {EXPLORATORY_NOTE}", "",
             f"## Gate (ADR-009): **{payload['n_total']} ops → {payload['validity']}**", "",
             f"lag_swings={payload['lag_swings']}  ·  Salidas vía trailing (no target ni stop original): {payload['rescued']}",
             "", "## V3+Trailing NETO por cohorte", payload["net"].to_string(index=False)]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    config = ingest.load_config()
    payload = run(config)
    print("=== Backtest V3 + trailing stop por estructura (ADR-013) — EXPLORATORIO ===")
    print(f"GATE: {payload['n_total']} operaciones → {payload['validity']}")
    print(f"Salidas vía trailing: {payload['rescued']}")
    print(payload["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
