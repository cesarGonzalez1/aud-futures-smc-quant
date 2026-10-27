"""Backtest V3 + gestión de breakeven móvil (ADR-012). EXPLORATORIO.

Misma señal/entrada/stop-inicial/target que V3 (ADR-009) — CERO cambios ahí. La
única diferencia es la GESTIÓN de la operación después de entrar: el stop se
mueve a breakeven (precio de entrada) la primera vez que el precio se mueve a
favor ≥0.4R (aprox. de "primer swing cercano, ~0.3-0.5R" — regla real del
usuario, ver `strategy/trade_management.py`). Sin salidas parciales.

Motivación: en V1-V5, `avg_loss` ronda −1.0R a −1.2R en TODAS las versiones —
ninguna "rescata" una operación que se movió a favor y luego se revirtió. Esta es
la hipótesis de que la brecha entre "el plan es rentable operado a mano" y "el
backtest da negativo" está en la gestión, no en la señal de entrada.

Guarda `experiments/<fecha>_strat_liq_sweep_amd_m5_v3_breakeven/` sin tocar V3.

Ejecución:  python -m backtest.run_v3_be
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import _prepare_m5, validity_label
from data import ingest
from strategy import liquidity_sweep_ifvg_v3 as v3
from strategy.trade_management import DEFAULT_BREAKEVEN_TRIGGER_R, apply_breakeven_management


def run(config: dict | None = None, breakeven_trigger_r: float = DEFAULT_BREAKEVEN_TRIGGER_R) -> dict:
    config = config or ingest.load_config()
    m5, bias, man = _prepare_m5(config)

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    trades = v3.generate_trades_v3(m5, bias)
    pois = getattr(v3.generate_trades_v3, "_last_pois", None)
    trades_be = apply_breakeven_management(trades, m5, breakeven_trigger_r=breakeven_trigger_r)

    t3 = v3.trades_to_frame(trades_be, pois)
    t3 = metrics.apply_costs(t3, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)

    rescued = int((t3["outcome"] == "breakeven").sum()) if "outcome" in t3.columns else 0

    return {
        "trades": t3, "net": metrics.metrics_by_cohort(t3, r_col="r_net"),
        "n_total": len(t3), "validity": validity_label(len(t3)),
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": man.sha256, "role": man.role,
        "breakeven_trigger_r": breakeven_trigger_r, "rescued": rescued,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_amd_m5_v3_breakeven"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: V3 + gestion breakeven movil (ADR-012), misma senal/entrada/target que V3\n"
        f"breakeven_trigger_r: {payload['breakeven_trigger_r']}\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"n_total: {payload['n_total']}\n"
        f"rescued_from_full_stop: {payload['rescued']}\n"
        f"validity_gate: \"{payload['validity']}\"\n"
        f"half_spread: {payload['half_spread']:.6f}\n"
        f"atr_ref: {payload['atr_ref']:.6f}\n"
        "deflated_sharpe: no aplica (una hipotesis predefinida, ADR-012)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n", encoding="utf-8")
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [f"# Backtest V3 + breakeven móvil (ADR-012) — {ts.date().isoformat()}", "",
             f"> {EXPLORATORY_NOTE}", "",
             f"## Gate (ADR-009): **{payload['n_total']} ops → {payload['validity']}**", "",
             f"Breakeven trigger: {payload['breakeven_trigger_r']}R  ·  "
             f"Operaciones rescatadas del stop completo: {payload['rescued']}", "",
             "## V3+BE NETO por cohorte", payload["net"].to_string(index=False)]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    config = ingest.load_config()
    payload = run(config)
    print(f"=== Backtest V3 + breakeven móvil (ADR-012) — EXPLORATORIO ===")
    print(f"GATE: {payload['n_total']} operaciones → {payload['validity']}")
    print(f"Rescatadas del stop completo por breakeven: {payload['rescued']}")
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
