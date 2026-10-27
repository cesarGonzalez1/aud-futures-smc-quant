"""Régimen vs baseline GARCH(1,1) WALK-FORWARD (Fase 3, ADR-003 enmienda).

Corrige la asimetría point-in-time del GARCH in-sample: aquí el baseline solo usa
datos hasta `t` (refit periódico). Compara, lado a lado y por cohorte, la
significancia del régimen sobre el residual in-sample vs. walk-forward.

Escribe un experimento NUEVO (`experiments/<fecha>_regime_vs_garch_walkforward/`).
NO toca los experimentos previos: el in-sample se conserva como análisis de
sensibilidad (sección 12: el conocimiento superado no se borra).

Ejecución:  python -m analysis.run_garch_wf
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analysis import garch_baseline as gb
from analysis import regime as regime_mod
from analysis import validation
from analysis.cohorts import COHORT_COL, add_cohort
from analysis.run import PROXY_WARNING, TARGET_COL
from data import ingest, schema
from data.storage import parquet_store
from data.storage.manifest import read_manifest

REGIME_COLS = (regime_mod.VOL_COL, regime_mod.REGIME_COL)
SIG = 0.05
REFIT_EVERY = 168   # semanal en H1 (configurable)
MIN_TRAIN = 1000
WINDOW = "expanding"


def analyze(config: dict | None = None) -> dict:
    config = config or ingest.load_config()
    feat_base = config["paths"]["features"]
    symbol = config["instruments"]["primary"]["symbol"]
    df = parquet_store.read_dataset(feat_base, symbol, "H1")
    man = read_manifest(parquet_store.dataset_dir(feat_base, symbol, "H1"))

    df = add_cohort(df, mode=config["cohorts"]["mode"])
    df = regime_mod.add_regime(df)

    # Pronóstico walk-forward: se calcula UNA vez (caro) y se reusa por régimen.
    fc_wf = gb.garch_forecast_vol_walkforward(
        df[schema.CLOSE], horizon=6, refit_every=REFIT_EVERY, min_train=MIN_TRAIN, window=WINDOW,
    )
    resid_wf = df[TARGET_COL] - fc_wf
    wf_coverage = float(fc_wf.notna().mean())

    out: dict[str, dict[str, pd.DataFrame]] = {}
    for col in REGIME_COLS:
        raw = validation.validate_regime_predictive(df, regime_col=col, target_col=TARGET_COL)
        insample = gb.validate_regime_over_garch_residual(df, regime_col=col, target_col=TARGET_COL)
        tmp = df[[col, COHORT_COL]].copy()
        tmp["garch_resid"] = resid_wf
        walkfwd = gb._kw_fdr_by_cohort(tmp, col, "garch_resid", min_sample=100)
        out[col] = {"raw": raw, "insample": insample, "walkforward": walkfwd}

    return {"results": out, "dataset_sha256": man.sha256, "role": man.role,
            "rows": len(df), "wf_coverage": wf_coverage}


def _compare(d: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Tabla comparativa por cohorte: cruda vs in-sample vs walk-forward."""
    m = (d["raw"][["cohort", "p_fdr"]].rename(columns={"p_fdr": "p_fdr_raw"})
         .merge(d["insample"][["cohort", "p_fdr"]].rename(columns={"p_fdr": "p_fdr_insample"}), on="cohort")
         .merge(d["walkforward"][["cohort", "p_fdr", "epsilon2"]]
                .rename(columns={"p_fdr": "p_fdr_wf", "epsilon2": "epsilon2_wf"}), on="cohort"))
    m["veredicto_wf"] = m.apply(
        lambda r: "aporta sobre GARCH-wf" if r["p_fdr_wf"] < SIG else "no aporta sobre GARCH-wf",
        axis=1,
    )
    return m


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_regime_vs_garch_walkforward"
    exp.mkdir(parents=True, exist_ok=True)

    (exp / "config.yaml").write_text(
        "objetivo: aporte del regimen sobre baseline GARCH(1,1) WALK-FORWARD (point-in-time)\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"target: {TARGET_COL}\n"
        f"baseline: GARCH(1,1) walk-forward via arch (window={WINDOW}, refit_every={REFIT_EVERY}, min_train={MIN_TRAIN})\n"
        f"wf_coverage: {payload['wf_coverage']:.4f}\n"
        f"regime_cols: {list(REGIME_COLS)}\n"
        f"proxy_warning: \"{PROXY_WARNING}\"\n",
        encoding="utf-8",
    )
    results_json = {c: {k: v.to_dict(orient="records") for k, v in d.items()}
                    for c, d in payload["results"].items()}
    (exp / "results.json").write_text(json.dumps(results_json, indent=2, default=str), encoding="utf-8")

    lines = [
        f"# Régimen vs GARCH(1,1) walk-forward — {ts.date().isoformat()}", "",
        f"> {PROXY_WARNING}", "",
        "**Conclusión primaria:** este experimento REEMPLAZA al in-sample "
        "(`_regime_vs_garch`) como conclusión de referencia, por corregir la asimetría "
        "point-in-time del baseline (GARCH ajustado solo con datos ≤ t, refit "
        f"{REFIT_EVERY} barras, ventana {WINDOW}). El in-sample se CONSERVA como "
        "análisis de sensibilidad (sección 12), no se borra.", "",
        f"Cobertura walk-forward (barras con pronóstico): {payload['wf_coverage']:.1%}.", "",
    ]
    for col, d in payload["results"].items():
        lines += [f"## {col}", "", "### Comparativa por cohorte (cruda / in-sample / walk-forward)",
                  _compare(d).to_string(index=False), "",
                  "### KW sobre residual walk-forward", d["walkforward"].to_string(index=False), ""]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    config = ingest.load_config()
    payload = analyze(config)
    print(f"=== Régimen vs GARCH walk-forward — {payload['rows']} filas, role={payload['role']} ===")
    print(f"> {PROXY_WARNING}")
    print(f"Cobertura walk-forward: {payload['wf_coverage']:.1%}\n")
    for col, d in payload["results"].items():
        print(f"--- {col} ---")
        print(_compare(d).to_string(index=False, float_format=lambda x: f"{x:.3g}"))
        print()
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
