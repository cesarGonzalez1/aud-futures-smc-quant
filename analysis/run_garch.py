"""Comparación régimen vs. baseline GARCH(1,1) (Fase 3, ADR-003 enmienda).

Corre, por cohorte, la validación del régimen (a) sobre la volatilidad cruda y
(b) sobre el RESIDUAL de un pronóstico GARCH(1,1). Si el régimen deja de ser
significativo sobre el residual, el régimen no aporta más allá de GARCH.

Escribe un experimento NUEVO (`experiments/<fecha>_regime_vs_garch/`); NO
sobrescribe el experimento previo de persistencia (conocimiento acumulado).

Ejecución:  python -m analysis.run_garch
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analysis import garch_baseline, regime as regime_mod, validation
from analysis.cohorts import add_cohort
from analysis.run import PROXY_WARNING, TARGET_COL
from data import ingest
from data.storage import parquet_store
from data.storage.manifest import read_manifest

REGIME_COLS = (regime_mod.VOL_COL, regime_mod.REGIME_COL)
SIG = 0.05


def analyze(config: dict | None = None) -> dict:
    config = config or ingest.load_config()
    feat_base = config["paths"]["features"]
    symbol = config["instruments"]["primary"]["symbol"]
    df = parquet_store.read_dataset(feat_base, symbol, "H1")
    man = read_manifest(parquet_store.dataset_dir(feat_base, symbol, "H1"))

    df = add_cohort(df, mode=config["cohorts"]["mode"])
    df = regime_mod.add_regime(df)

    out: dict[str, dict[str, pd.DataFrame]] = {}
    for col in REGIME_COLS:
        raw = validation.validate_regime_predictive(df, regime_col=col, target_col=TARGET_COL)
        resid = garch_baseline.validate_regime_over_garch_residual(
            df, regime_col=col, target_col=TARGET_COL,
        )
        out[col] = {"raw": raw, "garch_residual": resid}
    return {"results": out, "dataset_sha256": man.sha256, "role": man.role, "rows": len(df)}


def _verdict(raw: pd.DataFrame, resid: pd.DataFrame) -> pd.DataFrame:
    """Compara significancia (FDR) cruda vs. sobre residual GARCH, por cohorte."""
    m = raw[["cohort", "p_fdr", "epsilon2"]].merge(
        resid[["cohort", "p_fdr", "epsilon2"]], on="cohort", suffixes=("_raw", "_resid")
    )
    m["sig_raw"] = m["p_fdr_raw"] < SIG
    m["sig_sobre_garch"] = m["p_fdr_resid"] < SIG
    m["veredicto"] = m.apply(
        lambda r: "aporta sobre GARCH" if r["sig_sobre_garch"]
        else ("solo persistencia/GARCH" if r["sig_raw"] else "no significativo"),
        axis=1,
    )
    return m


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_regime_vs_garch"
    exp.mkdir(parents=True, exist_ok=True)

    (exp / "config.yaml").write_text(
        "objetivo: aisla el aporte del regimen sobre baseline GARCH(1,1) (ADR-003 enmienda)\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"target: {TARGET_COL}\n"
        "baseline: GARCH(1,1) via arch, in-sample por cohorte\n"
        f"regime_cols: {list(REGIME_COLS)}\n"
        f"proxy_warning: \"{PROXY_WARNING}\"\n",
        encoding="utf-8",
    )
    results_json = {
        col: {k: v.to_dict(orient="records") for k, v in d.items()}
        for col, d in payload["results"].items()
    }
    (exp / "results.json").write_text(json.dumps(results_json, indent=2, default=str), encoding="utf-8")

    lines = [f"# Régimen vs baseline GARCH(1,1) — {ts.date().isoformat()}", "", f"> {PROXY_WARNING}", ""]
    for col, d in payload["results"].items():
        lines += [f"## {col}", "", "### Veredicto por cohorte", _verdict(d["raw"], d["garch_residual"]).to_string(index=False), "",
                  "### KW sobre residual GARCH", d["garch_residual"].to_string(index=False), ""]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    config = ingest.load_config()
    payload = analyze(config)
    print(f"=== Régimen vs GARCH(1,1) — {payload['rows']} filas, role={payload['role']} ===")
    print(f"> {PROXY_WARNING}\n")
    for col, d in payload["results"].items():
        print(f"--- {col}: veredicto por cohorte ---")
        v = _verdict(d["raw"], d["garch_residual"])
        print(v[["cohort", "p_fdr_raw", "p_fdr_resid", "epsilon2_resid", "veredicto"]].to_string(
            index=False, float_format=lambda x: f"{x:.3g}"))
        print()
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
