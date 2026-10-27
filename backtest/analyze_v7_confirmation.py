"""Análisis (ADR-015): ¿MSS y CISD, por separado, tienen distinta expectativa
dentro de V7?

NO es una estrategia nueva ni cambia ninguna regla de generación de trades —
es un desglose retrospectivo de las MISMAS 197 operaciones de V7 (idéntica
entrada/stop/target), agrupadas por `confirmation_source` (qué confirmó
primero: MSS o CISD). Válido sin look-ahead porque `confirmation_source` ya es
un atributo grabado por operación en el momento en que V7 las generó — no se
recalcula nada distinto, solo se re-agrupa lo ya existente (mismo principio que
el desglose por `confidence` en V5/ADR-011).

Uso:
  python -m backtest.analyze_v7_confirmation
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import validity_label
from backtest.run_v7 import run
from data import ingest


def main() -> None:
    config = ingest.load_config()
    payload = run(config)
    trades = payload["trades"]

    print("=== V7 — desglose por fuente de confirmación (MSS vs CISD), ADR-015 ===")
    print(f"(mismas {payload['n_total']} operaciones de V7, sin cambios en la generación)\n")

    rows = []
    for source, g in trades.groupby("confirmation_source"):
        m = metrics.compute_metrics(g, r_col="r_net")
        rows.append({"confirmation_source": source, **m})
        gate = validity_label(m["n_trades"])
        print(f"--- {source} ({m['n_trades']} ops → {gate}) ---")
        print(f"  win_rate={m['win_rate']:.3f}  expectancy={m['expectancy']:.3f}R  "
              f"avg_win={m['avg_win']:.3f}R  avg_loss={m['avg_loss']:.3f}R  "
              f"max_drawdown_r={m['max_drawdown_r']:.2f}")

    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_analysis_v7_mss_vs_cisd"
    exp.mkdir(parents=True, exist_ok=True)
    import pandas as pd
    out = pd.DataFrame(rows)
    out.to_json(exp / "results.json", orient="records", indent=2)
    lines = [
        f"# Análisis V7 — MSS vs CISD (ADR-015) — {ts.date().isoformat()}", "",
        f"> {EXPLORATORY_NOTE} Desglose retrospectivo de las mismas operaciones de V7, no una hipótesis nueva.", "",
        out.to_string(index=False),
    ]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"\nGuardado en: {exp}")


if __name__ == "__main__":
    main()
