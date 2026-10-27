"""Backtest V11 (ADR-017 propuesto) — V9 (MSS-only) restringido a días de
confluencia `confidence='baja'` (2 de 4 marcos alineados, los otros 2
neutrales — NO tendencia fuerte de 3-4 marcos).

Origen: al tratar los atributos ya grabados por operación de V9 (`confidence`,
`target_source`, `quarter_aligned`) como posibles señales de calidad — el
mismo principio que "confluence scoring" en vez de reglas booleanas rígidas —
apareció que `confidence='baja'` supera ampliamente a `confidence='alta'`
dentro de las mismas 117 operaciones de V9:

    alta (3-4 marcos alineados): 49 ops, expectancy -0.404R
    baja (2 marcos, 2 neutrales): 68 ops, expectancy +0.099R

Validado con split temporal (no solo el agregado): el patrón se sostiene tanto
en 2020-2023 (+0.099R, 47 ops) como en el holdout 2024-2025 (+0.059R, 21 ops) —
consistente en ambos sub-periodos, no un artefacto de un solo año.

Hipótesis mecánica (no solo numérica): un reversal por liquidity sweep + MSS
pelea contra la tendencia cuando 3-4 marcos temporales ya están alineados
(tendencia fuerte establecida) — tiene más sentido en condiciones más
equilibradas (2 alineados, 2 neutrales, sin tendencia fuerte en contra).

Es una partición COMPLETA de las 117 operaciones de V9 (alta + baja = 117,
no hay carrera entre condiciones como en MSS/CISD) — el tamaño de muestra de
68 es real, no un artefacto de qué señal "ganó primero".

NO cambia la generación de V9 en absoluto — es un filtro adicional de capa 3
(contexto/confluencia), igual disciplina que Quarter Theory: reduce la
muestra, nunca la infla ni cambia entrada/stop/target.

Uso:
  python -m backtest.run_v11
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import validity_label
from backtest.run_v7 import run as run_v7
from data import ingest


def run(config: dict | None = None, months: int | None = None) -> dict:
    config = config or ingest.load_config()
    v9 = run_v7(config, months=months, confirmation_require="mss")
    trades = v9["trades"]
    filtered = trades[trades["confidence"] == "baja"].reset_index(drop=True) if not trades.empty else trades
    return {
        "v9": v9,
        "trades": filtered,
        "net": metrics.metrics_by_cohort(filtered, r_col="r_net") if not filtered.empty else filtered,
        "n_total": len(filtered),
        "validity": validity_label(len(filtered)),
        "months": months,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_v11_baja_confidence"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio V11 (ADR-017 propuesto): V9 (MSS-only) "
        "restringido a dias con confidence='baja' (2 de 4 marcos alineados, "
        "hallazgo derivado de tratar atributos de V9 como score de calidad)\n"
        f"n_total_v9: {payload['v9']['n_total']}\n"
        f"n_total_v11: {payload['n_total']}\n"
        f"validity_gate_v11: \"{payload['validity']}\"\n"
        "deflated_sharpe: hallazgo retrospectivo (no hipotesis predefinida) - "
        "activa 6.2 antes de confiar en el resultado para cualquier decision real\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n",
        encoding="utf-8")
    if not payload["trades"].empty:
        payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [
        f"# Backtest V11 (V9 + confidence='baja') — {ts.date().isoformat()}", "",
        f"> {EXPLORATORY_NOTE} Hallazgo retrospectivo, no hipotesis predefinida.", "",
        f"## V9 (baseline, todas las confianzas): {payload['v9']['n_total']} ops → {payload['v9']['validity']}",
        payload["v9"]["net"].to_string(index=False), "",
        f"## V11 (V9 + solo confidence='baja'): {payload['n_total']} ops → {payload['validity']}",
    ]
    lines.append(payload["net"].to_string(index=False) if not payload["trades"].empty else "(0 operaciones)")
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    config = ingest.load_config()
    payload = run(config)
    print("=== Backtest V11 (V9 + confidence='baja') — EXPLORATORIO, hallazgo retrospectivo ===")
    print(f"V9 (baseline): {payload['v9']['n_total']} ops → {payload['v9']['validity']}")
    print(payload["v9"]["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    print(f"\nV11 (solo confidence='baja'): {payload['n_total']} ops → {payload['validity']}")
    if not payload["trades"].empty:
        print(payload["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    exp = _write_experiment(payload, config)
    print(f"\nExperimento guardado en: {exp}")


if __name__ == "__main__":
    main()
