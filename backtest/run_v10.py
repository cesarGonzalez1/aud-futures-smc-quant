"""Backtest V10 (ADR-016) — V9 (MSS-only) + SMT (6A vs 6N) como gate diario.

Requiere que ya hayas corrido `make ingest` (o `python -m data.ingest`) en TU
entorno con 6N registrado en `config/settings.yaml` (ADR-016) — este script
falla explícitamente si no encuentra `data/raw/6N/D1` en disco, en vez de
generar un resultado silenciosamente vacío o parcial.

Compara, para que quede honesto en el mismo reporte:
  - V9 (baseline, sin SMT) — el mejor real hasta ahora (ADR-015).
  - V10 (V9 + gate diario SMT) — mismas operaciones de V9, filtradas por
    alineación SMT del día.

Guarda `experiments/<fecha>_strat_liq_sweep_v10_smt_gate/`.

Uso:
  python -m backtest.run_v10              # 5 años completos
  python -m backtest.run_v10 --months 3   # ventana corta (humo)
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import validity_label
from backtest.run_v7 import run as run_v7
from data import ingest
from data.storage import parquet_store
from features.smt import add_smt_divergence
from strategy.liquidity_sweep_ifvg_v10 import filter_trades_by_smt


def _load_smt(config: dict):
    raw = config["paths"]["raw"]
    real_symbol = config["instruments"]["real_asset"]["symbol"]  # "6A"
    try:
        a_d1 = parquet_store.read_dataset(raw, real_symbol, "D1")
        b_d1 = parquet_store.read_dataset(raw, "6N", "D1")
    except FileNotFoundError as exc:
        raise SystemExit(
            "No encontré 6N (o 6A) en data/raw/. Corre primero, en TU entorno:\n"
            "    make ingest\n"
            "(6N ya está registrado en config/settings.yaml, ADR-016). "
            f"Detalle: {exc}"
        ) from exc
    if a_d1.empty or b_d1.empty:
        raise SystemExit(
            "6A o 6N están vacíos en data/raw/ — revisa la salida de `make ingest` "
            "(¿algún error 403/404 al descargar de Yahoo?)."
        )
    return add_smt_divergence(a_d1, b_d1)


def run(config: dict | None = None, months: int | None = None) -> dict:
    config = config or ingest.load_config()
    v9 = run_v7(config, months=months, confirmation_require="mss")

    smt_daily = _load_smt(config)
    filtered = filter_trades_by_smt(v9["trades"], smt_daily)

    return {
        "v9": v9,
        "trades": filtered,
        "net": metrics.metrics_by_cohort(filtered, r_col="r_net") if not filtered.empty else filtered,
        "n_total": len(filtered),
        "validity": validity_label(len(filtered)),
        "smt_days_available": int(smt_daily[["smt_bear", "smt_bull"]].any(axis=1).sum()),
        "months": months,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_v10_smt_gate"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio V10 (ADR-016): V9 (MSS-only) + SMT (6A vs "
        "6N) como gate diario adicional, no cambia entrada/stop/target de V9\n"
        f"n_total_v9: {payload['v9']['n_total']}\n"
        f"n_total_v10: {payload['n_total']}\n"
        f"validity_gate_v10: \"{payload['validity']}\"\n"
        f"dias_con_smt_confirmado: {payload['smt_days_available']}\n"
        "deflated_sharpe: no aplica todavia (hipotesis predefinida ADR-015/016)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n",
        encoding="utf-8")
    if not payload["trades"].empty:
        payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [
        f"# Backtest V10 (ADR-016, SMT gate sobre V9) — {ts.date().isoformat()}", "",
        f"> {EXPLORATORY_NOTE}", "",
        f"## V9 (baseline, sin SMT): {payload['v9']['n_total']} ops → {payload['v9']['validity']}",
        payload["v9"]["net"].to_string(index=False), "",
        f"## V10 (V9 + gate SMT): {payload['n_total']} ops → {payload['validity']}",
    ]
    lines.append(payload["net"].to_string(index=False) if not payload["trades"].empty else "(0 operaciones)")
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    months = None
    if "--months" in sys.argv:
        months = int(sys.argv[sys.argv.index("--months") + 1])
    config = ingest.load_config()
    payload = run(config, months=months)
    tag = f" (ventana {months} meses)" if months else " (5 años)"
    print(f"=== Backtest V10 (ADR-016, SMT gate sobre V9){tag} — EXPLORATORIO ===")
    print(f"V9 (baseline, sin SMT): {payload['v9']['n_total']} ops → {payload['v9']['validity']}")
    print(payload["v9"]["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    print(f"\nV10 (V9 + gate SMT): {payload['n_total']} ops → {payload['validity']}")
    if not payload["trades"].empty:
        print(payload["net"].to_string(index=False, float_format=lambda x: f"{x:.3g}"))
    else:
        print("(0 operaciones sobreviven el gate SMT)")
    exp = _write_experiment(payload, config)
    print(f"\nExperimento guardado en: {exp}")


if __name__ == "__main__":
    main()
