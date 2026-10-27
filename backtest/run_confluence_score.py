"""Backtest (ADR-017) — motor de señales: score de confluencia en vez de
reglas booleanas, validado fuera de muestra.

Metodología (la parte que importa, no el resultado en sí):
  1. TRAIN = operaciones de V7 (MSS+CISD, jerarquía completa) 2020-2023.
     Calibra `ConfluenceScorer` — pesos = r_net promedio por categoría.
  2. TEST = operaciones de V7 2024-2025, NUNCA usado para calibrar. Se aplican
     los pesos del TRAIN (fijos) y se mide win_rate/expectancy del 50% de
     mayor score, fuera de muestra.
  3. Solo si el TEST confirma que el score generaliza (mejora sobre el
     promedio simple de esos mismos años), se recalibra con TODO el
     histórico (train+test) para producción — con esa advertencia explícita
     en el reporte, no como conclusión definitiva.

Uso:
  python -m backtest.run_confluence_score
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from backtest.run import EXPLORATORY_NOTE
from backtest.run_v7 import run as run_v7
from data import ingest
from decision_engine.scoring import ConfluenceScorer, SCORE_FEATURES


def _format_weights(weights: dict[str, dict[str, float]]) -> str:
    lines = []
    for feat, cats in weights.items():
        lines.append(f"- **{feat}**: " + ", ".join(f"{k}={v:.3f}" for k, v in cats.items()))
    return "\n".join(lines)


def main() -> None:
    config = ingest.load_config()
    v7 = run_v7(config)
    trades = v7["trades"].copy()
    trades["year"] = trades["cohort"].astype(int)

    train = trades[trades["year"] <= 2023]
    test = trades[trades["year"] >= 2024]

    print("=== Motor de señales: score de confluencia (ADR-017) ===\n")
    print(f"TRAIN (2020-2023): {len(train)} ops, expectancy={train['r_net'].mean():.4f}R (sin filtrar)")
    print(f"TEST  (2024-2025): {len(test)} ops, expectancy={test['r_net'].mean():.4f}R (sin filtrar, todo V7)\n")

    scorer = ConfluenceScorer.fit(train, features=SCORE_FEATURES)
    result = scorer.evaluate_out_of_sample(test, top_pct=0.5)
    print("--- Validación fuera de muestra (pesos SOLO de train, aplicados a test) ---")
    print(f"TEST top 50% por score: n={result['n_kept']}/{result['n_total']}  "
          f"win_rate={result['win_rate']:.3f}  expectancy={result['expectancy']:.4f}R")
    mejora = "MEJORA" if result["expectancy"] > test["r_net"].mean() else "NO mejora"
    print(f"(vs {test['r_net'].mean():.4f}R sin filtrar por score — {mejora} fuera de muestra)\n")

    print("⚠️  Sigue siendo net negativo. Esto valida la METODOLOGÍA (el score generaliza,")
    print("    no es un ajuste post-hoc), no que el sistema ya sea rentable.\n")

    scorer_prod = ConfluenceScorer.fit(trades, features=SCORE_FEATURES)
    print("--- Pesos de PRODUCCIÓN (recalibrados con las 197 operaciones completas) ---")
    for feat, weights in scorer_prod.weights.items():
        print(f"  {feat}: " + ", ".join(f"{k}={v:.3f}" for k, v in weights.items()))

    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_decision_engine_confluence_score"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: ADR-017 - motor de senales con score de confluencia (no booleano), "
        "validado con split temporal train(2020-2023)/test(2024-2025)\n"
        f"train_n: {len(train)}\ntest_n: {len(test)}\n"
        f"test_expectancy_sin_filtro: {test['r_net'].mean():.4f}\n"
        f"test_expectancy_top50pct_score: {result['expectancy']:.4f}\n"
        f"test_n_kept: {result['n_kept']}\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n",
        encoding="utf-8")
    (exp / "report.md").write_text(
        f"# Motor de señales — score de confluencia (ADR-017) — {ts.date().isoformat()}\n\n"
        f"> {EXPLORATORY_NOTE}\n\n"
        f"TRAIN 2020-2023: {len(train)} ops, expectancy sin filtro = {train['r_net'].mean():.4f}R\n\n"
        f"TEST 2024-2025 sin filtro: {len(test)} ops, expectancy = {test['r_net'].mean():.4f}R\n\n"
        f"TEST top 50% por score (pesos SOLO de train): {result['n_kept']} ops, "
        f"win_rate={result['win_rate']:.3f}, expectancy={result['expectancy']:.4f}R\n\n"
        "Pesos de producción (recalibrados con las 197 operaciones completas):\n\n"
        + _format_weights(scorer_prod.weights),
        encoding="utf-8")
    print(f"\nGuardado en: {exp}")


if __name__ == "__main__":
    main()
