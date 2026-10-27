"""Backtest (ADR-015) — V9 (MSS-only) combinado con las variantes de target/stop
que ya se probaron sobre V7 "cualquiera" y resultaron peores ahí. Pregunta:
¿se comportan distinto con una confirmación más selectiva (MSS-only)?

⚠️ Exploratorio, ajuste sobre un eje ya tocado 3 veces (any/cisd/mss) más 2
veces en target (V7/V7b) y 2 en stop (V7/V8) — con V9 ya son varias variantes
comparadas; cualquier mejora aquí necesita, antes de usarse para decidir algo
real, el control formal de tests múltiples (Deflated Sharpe, sección 6.2).

Variantes:
  V9        = V7 + confirmation_require='mss'                      (baseline ya conocido)
  V9b       = V9 + quarter_n_levels=2                               (target más lejos)
  V9-stopM5 = V9 con stop en swing M5 (igual V8) + min_stop_atr_frac (realismo)

Uso:
  python -m backtest.run_v9_combinations
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import validity_label
from backtest.run_v7 import run as run_v7
from backtest.run_v8 import run as run_v8
from data import ingest


def _print_row(name: str, payload: dict) -> None:
    row = payload["net"].iloc[-1]
    print(f"--- {name} ---")
    print(f"  {payload['n_total']} operaciones → {payload['validity']}")
    print(f"  win_rate={row['win_rate']:.3f}  expectancy={row['expectancy']:.3f}R  "
          f"avg_win={row['avg_win']:.3f}R  avg_loss={row['avg_loss']:.3f}R  "
          f"max_drawdown_r={row['max_drawdown_r']:.2f}\n")


def main() -> None:
    config = ingest.load_config()
    print("=== V9 (MSS-only) combinado con target/stop ya explorados (ADR-015) ===\n")

    results = {}
    results["v9_baseline"] = run_v7(config, confirmation_require="mss")
    _print_row("V9 (MSS-only, baseline)", results["v9_baseline"])

    results["v9b_quarter2"] = run_v7(config, confirmation_require="mss", quarter_n_levels=2)
    _print_row("V9b (MSS-only + quarter_n_levels=2)", results["v9b_quarter2"])

    results["v9_stop_m5"] = run_v8(config, confirmation_require="mss")
    _print_row("V9-stopM5 (MSS-only + stop swing M5, con filtro ATR)", results["v9_stop_m5"])

    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_v9_combinations"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio (ADR-015): V9 (MSS-only) combinado con "
        "variantes de target (quarter_n_levels=2) y stop (swing M5) ya probadas "
        "sobre V7 'cualquiera' y descartadas ahi\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n",
        encoding="utf-8")
    lines = [f"# V9 combinaciones (ADR-015) — {ts.date().isoformat()}", "", f"> {EXPLORATORY_NOTE}", ""]
    for name, payload in results.items():
        lines += [f"## {name} — {payload['n_total']} ops → {payload['validity']}",
                   payload["net"].to_string(index=False), ""]
        payload["trades"].to_json(exp / f"results_{name}.json", orient="records", indent=2, date_format="iso")
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Guardado en: {exp}")


if __name__ == "__main__":
    main()
