"""Backtest V8 (ADR-015) — igual que V7, cambia SOLO el stop: swing M5 en vez
de swing H1. Ver docstring de `strategy/liquidity_sweep_ifvg_v8.py`.

Hipótesis predefinida ANTES de ver el resultado (no es un ajuste post-V7 como
V7b): V4-V7 siempre usaron swing H1 para el stop sin haber probado la
alternativa M5 que ya estaba disponible en el pipeline. Se prueba una vez, con
todo lo demás fijo.

Guarda `experiments/<fecha>_strat_liq_sweep_full_hierarchy_v8_stop_m5/`.

Uso:
  python -m backtest.run_v8              # 5 años completos
  python -m backtest.run_v8 --months 3   # ventana corta (humo)
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
from strategy import liquidity_sweep_ifvg_v8 as v8


def run(
    config: dict | None = None,
    months: int | None = None,
    confirmation_require: str = "any",
    quarter_n_levels: int = 1,
) -> dict:
    config = config or ingest.load_config()
    m5, h1, confluence, man, (window_start, window_end) = _prepare(config, months)
    m5 = add_mss_flags(m5)

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    trades, confidences, sources, confirmations, quarter_aligned = v8.generate_trades_v8(
        m5, h1, confluence, window_start=window_start, window_end=window_end,
        confirmation_require=confirmation_require, quarter_n_levels=quarter_n_levels,
    )
    t8 = v8.trades_to_frame(trades, confidences, sources, confirmations, quarter_aligned)
    t8 = metrics.apply_costs(t8, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)

    return {
        "trades": t8, "net": metrics.metrics_by_cohort(t8, r_col="r_net"),
        "n_total": len(t8), "validity": validity_label(len(t8)),
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": man.sha256, "role": man.role, "months": months,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_full_hierarchy_v8_stop_m5"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio V8 (ADR-015): igual que V7, stop en "
        "swing M5 en vez de swing H1 (hipotesis predefinida sobre el stop, no "
        "ajuste post-V7)\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"n_total: {payload['n_total']}\n"
        f"window_months: {payload['months']}\n"
        f"validity_gate: \"{payload['validity']}\"\n"
        "deflated_sharpe: no aplica todavia (hipotesis predefinida, primer intento "
        "sobre este eje); si se ajusta tras ver este resultado, activa 6.2\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n",
        encoding="utf-8")
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [
        f"# Backtest V8 (ADR-015, stop swing M5) — {ts.date().isoformat()}", "",
        f"> {EXPLORATORY_NOTE}", "",
        f"## Gate (ADR-009): **{payload['n_total']} ops → {payload['validity']}**", "",
        "## V8 NETO por cohorte", payload["net"].to_string(index=False),
    ]
    t = payload["trades"]
    if not t.empty:
        if "confirmation_source" in t.columns:
            lines += ["", "## V8 — operaciones por fuente de confirmación (MSS/CISD)",
                      t["confirmation_source"].value_counts().to_string()]
        if "target_source" in t.columns:
            lines += ["", "## V8 — operaciones por fuente de target",
                      t["target_source"].value_counts().to_string()]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    months = None
    if "--months" in sys.argv:
        months = int(sys.argv[sys.argv.index("--months") + 1])
    config = ingest.load_config()
    payload = run(config, months=months)
    tag = f" (ventana {months} meses)" if months else " (5 años)"
    print(f"=== Backtest V8 (ADR-015, stop swing M5){tag} — EXPLORATORIO ===")
    print(f"GATE: {payload['n_total']} operaciones → {payload['validity']}")
    print(payload["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
