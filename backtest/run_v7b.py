"""Backtest V7b (ADR-015, exploratorio) — ajuste de V7 tras ver su resultado.

⚠️ Este experimento AJUSTA un parámetro (`quarter_n_levels=2` en vez de 1)
DESPUÉS de haber visto el resultado de V7 (sección 6.2: control de tests
múltiples). Se documenta explícitamente como comparación V7 vs V7b, no como
hipótesis independiente predefinida — cualquier lectura de "V7b es mejor"
requiere, antes de usarse para decidir algo real, verificar que la mejora no es
ruido de una sola variante probada tras ver datos (idealmente con más
variantes comparadas y Deflated Sharpe, no solo dos puntos).

Motivación (diagnóstico de V7, `experiments/..._v7/report.md`): con
`quarter_n_levels=1` el target es el cuarto INMEDIATO (0.0025) — muy cercano
frente a un stop de swing H1 ancho, dando `avg_win` (0.67R) < `avg_loss`
(1.13R) pese a win rate 52.8%. Con `quarter_n_levels=2` el target salta un
cuarto (recorrido ~0.0050, casi una "big figure" completa) buscando subir
`avg_win` sin tocar el stop ni ninguna otra capa de la jerarquía.

Uso:
  python -m backtest.run_v7b
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import validity_label
from backtest.run_v7 import run
from data import ingest


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_full_hierarchy_v7b_quarter2"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio V7b (ADR-015): igual que V7 pero "
        "quarter_n_levels=2 (target salta un cuarto en vez del inmediato)\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"n_total: {payload['n_total']}\n"
        f"window_months: {payload['months']}\n"
        f"validity_gate: \"{payload['validity']}\"\n"
        "deflated_sharpe: NO aplicado todavia; este experimento AJUSTA un parametro "
        "tras ver el resultado de V7 -> activa 6.2, se documenta la comparacion V7 vs V7b\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n",
        encoding="utf-8")
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [
        f"# Backtest V7b (ADR-015, ajuste post-resultado sobre V7) — {ts.date().isoformat()}", "",
        f"> {EXPLORATORY_NOTE} Ademas: parametro ajustado tras ver V7 (seccion 6.2).", "",
        f"## Gate (ADR-009): **{payload['n_total']} ops → {payload['validity']}**", "",
        "## V7b NETO por cohorte", payload["net"].to_string(index=False),
    ]
    t = payload["trades"]
    if not t.empty and "target_source" in t.columns:
        lines += ["", "## V7b — operaciones por fuente de target", t["target_source"].value_counts().to_string()]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    months = None
    if "--months" in sys.argv:
        months = int(sys.argv[sys.argv.index("--months") + 1])
    config = ingest.load_config()
    payload = run(config, months=months, quarter_n_levels=2)
    tag = f" (ventana {months} meses)" if months else " (5 años)"
    print(f"=== Backtest V7b (ADR-015, quarter_n_levels=2){tag} — EXPLORATORIO, ajuste post-V7 ===")
    print(f"GATE: {payload['n_total']} operaciones → {payload['validity']}")
    print(payload["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
