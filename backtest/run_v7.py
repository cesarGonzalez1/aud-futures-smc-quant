"""Backtest V7 (ADR-015) — jerarquía discrecional completa del usuario.

Reutiliza la preparación de datos de V5 (`backtest.run_v5._prepare`) sin
tocarla: mismo bias de confluencia (D1/H4/NY AM/NY PM), mismo POI de equal
highs/lows, mismo stop (swing H1). Añade `mss_bull`/`mss_bear`
(`features.mss_cisd.add_mss_flags`) sobre M5, y usa
`strategy.liquidity_sweep_ifvg_v7.generate_trades_v7` (confirmación MSS/CISD +
objetivo con Quarter Theory + BOS).

Guarda `experiments/<fecha>_strat_liq_sweep_full_hierarchy_v7/` sin tocar V1-V6.

Uso:
  python -m backtest.run_v7              # 5 años completos
  python -m backtest.run_v7 --months 3    # ventana corta (humo)
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
from features.mss_cisd import add_mss_flags
from strategy import liquidity_sweep_ifvg_v7 as v7


def run(
    config: dict | None = None,
    months: int | None = None,
    quarter_n_levels: int = 1,
    confirmation_require: str = "any",
) -> dict:
    config = config or ingest.load_config()
    m5, h1, confluence, man, (window_start, window_end) = _prepare(config, months)
    m5 = add_mss_flags(m5)  # capa 2 (MSS), único requisito adicional sobre la preparación de V5

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    trades, confidences, sources, confirmations, quarter_aligned = v7.generate_trades_v7(
        m5, h1, confluence, window_start=window_start, window_end=window_end,
        quarter_n_levels=quarter_n_levels, confirmation_require=confirmation_require,
    )
    t7 = v7.trades_to_frame(trades, confidences, sources, confirmations, quarter_aligned)
    t7 = metrics.apply_costs(t7, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)

    return {
        "trades": t7, "net": metrics.metrics_by_cohort(t7, r_col="r_net"),
        "n_total": len(t7), "validity": validity_label(len(t7)),
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": man.sha256, "role": man.role, "months": months,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_full_hierarchy_v7"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio V7 (jerarquia discrecional completa: "
        "MSS/CISD + Quarter Theory + BOS, ADR-015)\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"n_total: {payload['n_total']}\n"
        f"window_months: {payload['months']}\n"
        f"validity_gate: \"{payload['validity']}\"\n"
        f"half_spread: {payload['half_spread']:.6f}\n"
        f"atr_ref: {payload['atr_ref']:.6f}\n"
        "deflated_sharpe: no aplica todavia (hipotesis predefinida ADR-015); "
        "SI se ajustan parametros tras ver este resultado, activa 6.2\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n"
        "nota_smt: \"SMT (6A vs 6N) pendiente por falta de datos 6N ingeridos (ver ADR-016 propuesto)\"\n",
        encoding="utf-8")
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [
        f"# Backtest V7 (jerarquía discrecional completa, ADR-015) — {ts.date().isoformat()}", "",
        f"> {EXPLORATORY_NOTE}", "",
        f"## Gate (ADR-009): **{payload['n_total']} ops → {payload['validity']}**", "",
        "## V7 NETO por cohorte", payload["net"].to_string(index=False),
    ]
    t = payload["trades"]
    if not t.empty:
        if "confirmation_source" in t.columns:
            lines += ["", "## V7 — operaciones por fuente de confirmación (MSS/CISD)",
                      t["confirmation_source"].value_counts().to_string()]
        if "target_source" in t.columns:
            lines += ["", "## V7 — operaciones por fuente de target",
                      t["target_source"].value_counts().to_string()]
        if "quarter_aligned" in t.columns:
            lines += ["", "## V7 — operaciones cerca de un nivel Quarter Theory (contexto, informativo)",
                      t["quarter_aligned"].value_counts().to_string()]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    months = None
    if "--months" in sys.argv:
        months = int(sys.argv[sys.argv.index("--months") + 1])
    config = ingest.load_config()
    payload = run(config, months=months)
    tag = f" (ventana {months} meses)" if months else " (5 años)"
    print(f"=== Backtest V7 (jerarquía discrecional completa, ADR-015){tag} — EXPLORATORIO ===")
    print(f"GATE: {payload['n_total']} operaciones → {payload['validity']}")
    print(payload["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
