"""Orquestador de análisis de régimen (Fase 3).

Lee el dataset de features (proxy AUD/USD H1), asigna cohortes, detecta régimen
por reglas (ADR-003) y valida su valor predictivo sobre el target de volatilidad
futura (con baseline, tamaño de efecto y FDR). Persiste un experimento
autocontenido (sección 12).

Ejecución:  python -m analysis.run

ADVERTENCIA DE PROXY (ADR-006): el régimen y la estructura se calculan sobre el
proxy spot AUD/USD, no sobre el futuro real 6A. Sweeps/sesiones/régimen pueden no
calzar 1:1 con la plataforma de futuros.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analysis import regime as regime_mod
from analysis import validation
from analysis.cohorts import add_cohort
from data import ingest
from data.storage import parquet_store
from data.storage.manifest import read_manifest

PROXY_WARNING = (
    "Estructura/régimen intradía basados en proxy spot AUD/USD, no en el contrato "
    "de futuros 6A directamente (ADR-006)."
)
TARGET_COL = "target_fwd_vol_6"
REGIME_COLS = (regime_mod.TREND_COL, regime_mod.VOL_COL, regime_mod.REGIME_COL)


def analyze(config: dict | None = None) -> dict:
    """Corre el análisis completo y devuelve resultados + metadatos."""
    config = config or ingest.load_config()
    feat_base = config["paths"]["features"]
    symbol = config["instruments"]["primary"]["symbol"]
    tf = "H1"

    df = parquet_store.read_dataset(feat_base, symbol, tf)
    feat_manifest = read_manifest(parquet_store.dataset_dir(feat_base, symbol, tf))

    df = add_cohort(df, mode=config["cohorts"]["mode"])
    df = regime_mod.add_regime(df)

    results: dict[str, pd.DataFrame] = {}
    for col in REGIME_COLS:
        results[col] = validation.validate_regime_predictive(
            df, regime_col=col, target_col=TARGET_COL,
        )

    return {
        "results": results,
        "dataset_sha256": feat_manifest.sha256,
        "role": feat_manifest.role,
        "rows": len(df),
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    """Persiste el experimento en experiments/<fecha>_regime_vol/ (sección 12)."""
    ts = datetime.now(timezone.utc)
    exp_dir = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_regime_vol"
    exp_dir.mkdir(parents=True, exist_ok=True)

    (exp_dir / "config.yaml").write_text(
        "objetivo: valor predictivo del regimen sobre volatilidad futura (ADR-003)\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"target: {TARGET_COL}\n"
        f"regime_cols: {list(REGIME_COLS)}\n"
        f"proxy_warning: \"{PROXY_WARNING}\"\n",
        encoding="utf-8",
    )
    results_json = {col: res.to_dict(orient="records") for col, res in payload["results"].items()}
    (exp_dir / "results.json").write_text(json.dumps(results_json, indent=2, default=str), encoding="utf-8")

    lines = [f"# Régimen vs volatilidad futura — {ts.date().isoformat()}", "", f"> {PROXY_WARNING}", ""]
    for col, res in payload["results"].items():
        lines.append(f"## {col}")
        lines.append(res.to_string(index=False))
        lines.append("")
    (exp_dir / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp_dir


def main() -> None:
    config = ingest.load_config()
    payload = analyze(config)
    print(f"=== Análisis de régimen (Fase 3) — {payload['rows']} filas, role={payload['role']} ===")
    print(f"> {PROXY_WARNING}\n")
    for col, res in payload["results"].items():
        print(f"--- {col} ---")
        cols = ["cohort", "n", "n_regimes", "dropped_regimes", "H", "p_raw", "p_fdr",
                "epsilon2", "baseline_spearman"]
        print(res[cols].to_string(index=False, float_format=lambda x: f"{x:.4g}"))
        print()
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
