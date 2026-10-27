"""Validación de valor predictivo del régimen (ADR-003 + enmienda Fase 3).

Responde al problema de circularidad: no se valida "accuracy de clasificación"
(no hay ground truth de régimen), sino si el régimen tiene valor predictivo sobre
el target (volatilidad realizada futura, sección 2). Por cohorte (6.4):

  - Kruskal-Wallis entre las distribuciones de target por régimen (no paramétrico).
  - **Tamaño de efecto** epsilon² (no solo el p-value).
  - **Baseline anti-tautología**: Spearman(vol realizada actual, target). Si el
    régimen no supera claramente esta persistencia, su "valor" puede ser trivial.
  - **N mínimo** por celda régimen×cohorte (default 100); se descartan las chicas.
  - **FDR (Benjamini-Hochberg)** sobre los p-values de todas las cohortes.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kruskal, spearmanr
from statsmodels.stats.multitest import multipletests

from analysis.cohorts import COHORT_COL


def epsilon_squared(h_stat: float, n: int, k: int) -> float:
    """Tamaño de efecto epsilon² de Kruskal-Wallis. NaN si n<=k."""
    if n <= k:
        return float("nan")
    return (h_stat - k + 1) / (n - k)


def validate_regime_predictive(
    df: pd.DataFrame,
    *,
    regime_col: str,
    target_col: str,
    persistence_col: str = "realized_vol",
    min_sample: int = 100,
) -> pd.DataFrame:
    """Corre la validación por cohorte y devuelve una tabla de resultados.

    Columnas del resultado: cohort, n, n_regimes, dropped_regimes, H, p_raw,
    p_fdr, epsilon2, baseline_spearman, note.
    """
    rows: list[dict] = []
    for cohort, g in df.groupby(COHORT_COL):
        sub = g[[regime_col, target_col, persistence_col]].dropna()
        grouped = list(sub.groupby(regime_col))
        kept = [(lab, v[target_col].to_numpy()) for lab, v in grouped if len(v) >= min_sample]
        dropped = len(grouped) - len(kept)

        base = np.nan
        # Spearman requiere variabilidad en ambas series (evita ConstantInputWarning).
        if len(sub) > 2 and sub[persistence_col].nunique() > 1 and sub[target_col].nunique() > 1:
            base, _ = spearmanr(sub[persistence_col], sub[target_col])

        if len(kept) < 2:
            rows.append({
                "cohort": cohort, "n": len(sub), "n_regimes": len(kept),
                "dropped_regimes": dropped, "H": np.nan, "p_raw": np.nan,
                "epsilon2": np.nan, "baseline_spearman": base,
                "note": "insuficientes regímenes con N mínimo",
            })
            continue

        h_stat, p = kruskal(*[arr for _, arr in kept])
        n = int(sum(len(arr) for _, arr in kept))
        k = len(kept)
        rows.append({
            "cohort": cohort, "n": n, "n_regimes": k, "dropped_regimes": dropped,
            "H": h_stat, "p_raw": p, "epsilon2": epsilon_squared(h_stat, n, k),
            "baseline_spearman": base, "note": "",
        })

    res = pd.DataFrame(rows)
    # FDR sobre las cohortes con p-value válido (control de tests múltiples, 6.2).
    res["p_fdr"] = np.nan
    mask = res["p_raw"].notna()
    if mask.any():
        res.loc[mask, "p_fdr"] = multipletests(
            res.loc[mask, "p_raw"].to_numpy(), method="fdr_bh"
        )[1]
    return res
