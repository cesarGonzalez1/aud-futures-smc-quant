"""Backtest V7 restringido a una sola fuente de confirmación (ADR-015).

A diferencia de `analyze_v7_confirmation.py` (desglose retrospectivo de las
197 operaciones de V7 mezclado), esto GENERA las operaciones exigiendo desde el
principio SOLO MSS o SOLO CISD (`confirmation_require`) — la otra fuente ni
siquiera compite por el timestamp de confirmación, así que el tamaño de
muestra y el resultado no dependen de "quién ganó la carrera" en V7 mezclado.

Motivación: el desglose retrospectivo mostró MSS con mejor expectativa
aparente (+0.207R) pero solo 27 operaciones (bajo el gate de 100, ADR-009) —
insuficiente para concluir nada. Esta corrida es la forma correcta de medir
qué tan grande sería realmente la muestra de "solo MSS" si fuera la única
confirmación exigida.

Uso:
  python -m backtest.run_v7_confirmation_split
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import validity_label
from backtest.run_v7 import run
from data import ingest


def main() -> None:
    config = ingest.load_config()
    print("=== V7 restringido por fuente de confirmación (ADR-015) — hipótesis independientes ===\n")

    results = {}
    for require in ("mss", "cisd"):
        payload = run(config, confirmation_require=require)
        results[require] = payload
        n = payload["n_total"]
        gate = payload["validity"]
        row = payload["net"].iloc[-1]  # fila ALL
        print(f"--- confirmation_require='{require}' ---")
        print(f"  {n} operaciones → {gate}")
        print(f"  win_rate={row['win_rate']:.3f}  expectancy={row['expectancy']:.3f}R  "
              f"avg_win={row['avg_win']:.3f}R  avg_loss={row['avg_loss']:.3f}R  "
              f"max_drawdown_r={row['max_drawdown_r']:.2f}\n")

    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_v7_confirmation_split"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio (ADR-015): V7 exigiendo SOLO MSS o SOLO "
        "CISD como confirmacion, para medir el tamano de muestra real de cada una "
        "por separado (no un desglose retrospectivo de V7 mezclado)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n",
        encoding="utf-8")
    lines = [f"# V7 por fuente de confirmación (ADR-015) — {ts.date().isoformat()}", "",
              f"> {EXPLORATORY_NOTE}", ""]
    for require, payload in results.items():
        lines += [f"## confirmation_require='{require}' — {payload['n_total']} ops → {payload['validity']}",
                    payload["net"].to_string(index=False), ""]
        payload["trades"].to_json(exp / f"results_{require}.json", orient="records", indent=2, date_format="iso")
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Guardado en: {exp}")


if __name__ == "__main__":
    main()
