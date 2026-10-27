"""Baseline GARCH(1,1) para el target de volatilidad (ADR-003 enmienda, Fase 3).

Baseline FUERTE contra el que medir si el régimen aporta información nueva. Usa la
librería `arch` (madura, no se reinventa). Dos variantes:

  - **in-sample** (`garch_forecast_vol`): un ajuste por cohorte sobre toda la
    cohorte. Rápido, pero usa datos de todo el período para pronosticar dentro de
    él → asimetría point-in-time. Se conserva solo como análisis de sensibilidad.
  - **walk-forward** (`garch_forecast_vol_walkforward`): ajusta solo con datos
    hasta `t`, refit periódico, y pronostica hacia adelante. Cumple el mismo
    estándar point-in-time que el régimen (6.1). Es la variante de referencia.

Comparación (ambas variantes): residual = vol realizada real − pronóstico GARCH;
luego Kruskal-Wallis + epsilon² + FDR por cohorte sobre ese residual. Si el régimen
deja de ser significativo sobre el residual, no aporta más allá de GARCH.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from arch import arch_model
from scipy.stats import kruskal
from statsmodels.stats.multitest import multipletests

from analysis.cohorts import COHORT_COL
from analysis.validation import epsilon_squared
from data import schema

_SCALE = 10000.0  # retornos H1 de FX son diminutos; escalar a puntos básicos deja
#                   la serie en el rango 1-1000 que arch recomienda para converger.


def _nbar_sum_var(sig2_next: np.ndarray | float, persist: float, omega: float, horizon: int):
    """Suma analítica de varianzas GARCH(1,1) de t+1..t+N dado σ²_{t+1}."""
    if persist < 1:
        vl = omega / (1 - persist)
        geo = (1 - persist**horizon) / (1 - persist)
        return horizon * vl + (sig2_next - vl) * geo
    return horizon * sig2_next  # sin reversión a la media


def _fit_garch(ret: pd.Series):
    """Ajusta GARCH(1,1) media constante; devuelve (res, omega, alpha, beta, mu)."""
    res = arch_model(ret, mean="constant", vol="GARCH", p=1, q=1, dist="normal").fit(disp="off")
    p = res.params
    return res, p["omega"], p["alpha[1]"], p["beta[1]"], p["mu"]


def garch_forecast_vol(close: pd.Series, horizon: int) -> pd.Series:
    """Pronóstico GARCH(1,1) in-sample (un ajuste sobre toda la serie dada).

    Devuelve, por barra t, sqrt de la suma esperada de varianzas t+1..t+horizon,
    en unidades de retorno log (comparable a `target_fwd_vol_N`).
    """
    ret = np.log(close).diff().dropna() * _SCALE
    if len(ret) < 50:
        return pd.Series(np.nan, index=close.index)
    res, omega, alpha, beta, mu = _fit_garch(ret)
    cond_var = np.asarray(res.conditional_volatility) ** 2
    resid = np.asarray(res.resid)
    sig2_next = omega + alpha * resid**2 + beta * cond_var
    sum_var = _nbar_sum_var(sig2_next, alpha + beta, omega, horizon)
    fwd = np.sqrt(np.clip(sum_var, 0, None)) / _SCALE
    return pd.Series(fwd, index=ret.index).reindex(close.index)


def garch_forecast_vol_walkforward(
    close: pd.Series,
    horizon: int,
    *,
    refit_every: int = 168,
    min_train: int = 1000,
    window: str = "expanding",
    moving_size: int | None = None,
) -> pd.Series:
    """Pronóstico GARCH(1,1) walk-forward, estrictamente point-in-time.

    En cada punto de refit se ajusta el modelo SOLO con retornos hasta ese punto;
    entre refits se filtra la varianza condicional hacia adelante con los retornos
    ya observados (≤ t) y se pronostica t+1..t+horizon. Ningún ajuste ni pronóstico
    usa datos posteriores a t.

    Args:
        refit_every: cadencia de reajuste en barras (default 168 = semanal en H1).
            No se reajusta barra por barra por costo computacional; es configurable.
        min_train: mínimo de barras de entrenamiento antes del primer pronóstico.
        window: "expanding" (default, documentado) o "moving".
        moving_size: tamaño de ventana móvil si window="moving".
    """
    if window not in ("expanding", "moving"):
        raise ValueError(f"window inválido: {window!r}")
    ret = np.log(close).diff().dropna() * _SCALE
    arr = ret.to_numpy()
    m = len(arr)
    fwd = np.full(m, np.nan)
    if m < min_train + 1:
        return pd.Series(fwd, index=ret.index).reindex(close.index)

    r = min_train
    while r < m:
        lo = 0 if window == "expanding" else max(0, r - (moving_size or min_train))
        try:
            res, omega, alpha, beta, mu = _fit_garch(ret.iloc[lo:r])
        except Exception:  # noqa: BLE001 - un refit que no converge se salta, se reporta como NaN
            r += refit_every
            continue
        persist = alpha + beta
        prev_sigma2 = float(np.asarray(res.conditional_volatility)[-1] ** 2)  # σ² en la barra r-1
        seg_end = min(r + refit_every, m)
        for t in range(r, seg_end):
            sigma2_t = omega + alpha * (arr[t - 1] - mu) ** 2 + beta * prev_sigma2
            sig2_next = omega + alpha * (arr[t] - mu) ** 2 + beta * sigma2_t
            sum_var = _nbar_sum_var(sig2_next, persist, omega, horizon)
            fwd[t] = np.sqrt(max(sum_var, 0.0)) / _SCALE
            prev_sigma2 = sigma2_t
        r = seg_end
    return pd.Series(fwd, index=ret.index).reindex(close.index)


def _kw_fdr_by_cohort(
    df: pd.DataFrame, regime_col: str, resid_col: str, min_sample: int
) -> pd.DataFrame:
    """KW + epsilon² + FDR del régimen sobre `resid_col`, por cohorte."""
    rows: list[dict] = []
    for cohort, g in df.groupby(COHORT_COL):
        sub = g[[regime_col, resid_col]].dropna()
        rmse = float(np.sqrt(np.mean(sub[resid_col].to_numpy() ** 2))) if len(sub) else np.nan
        grouped = list(sub.groupby(regime_col))
        kept = [(lab, v[resid_col].to_numpy()) for lab, v in grouped if len(v) >= min_sample]
        dropped = len(grouped) - len(kept)

        if len(kept) < 2:
            rows.append({"cohort": cohort, "n": len(sub), "n_regimes": len(kept),
                         "dropped_regimes": dropped, "H": np.nan, "p_raw": np.nan,
                         "epsilon2": np.nan, "garch_rmse": rmse,
                         "note": "insuficientes regímenes con N mínimo"})
            continue
        h_stat, p = kruskal(*[a for _, a in kept])
        n = int(sum(len(a) for _, a in kept))
        k = len(kept)
        rows.append({"cohort": cohort, "n": n, "n_regimes": k, "dropped_regimes": dropped,
                     "H": h_stat, "p_raw": p, "epsilon2": epsilon_squared(h_stat, n, k),
                     "garch_rmse": rmse, "note": ""})

    res = pd.DataFrame(rows)
    res["p_fdr"] = np.nan
    mask = res["p_raw"].notna()
    if mask.any():
        res.loc[mask, "p_fdr"] = multipletests(res.loc[mask, "p_raw"].to_numpy(), method="fdr_bh")[1]
    return res


def validate_regime_over_garch_residual(
    df: pd.DataFrame, *, regime_col: str, target_col: str,
    horizon: int = 6, close_col: str = schema.CLOSE, min_sample: int = 100,
) -> pd.DataFrame:
    """Validación sobre residual GARCH **in-sample** (un ajuste por cohorte)."""
    parts = []
    for _, g in df.groupby(COHORT_COL):
        fc = garch_forecast_vol(g[close_col], horizon)
        parts.append((g[target_col] - fc).rename("garch_resid"))
    resid = pd.concat(parts)
    tmp = df[[regime_col, COHORT_COL]].join(resid)
    return _kw_fdr_by_cohort(tmp, regime_col, "garch_resid", min_sample)


def validate_regime_over_garch_residual_walkforward(
    df: pd.DataFrame, *, regime_col: str, target_col: str,
    horizon: int = 6, close_col: str = schema.CLOSE, min_sample: int = 100,
    refit_every: int = 168, min_train: int = 1000, window: str = "expanding",
) -> pd.DataFrame:
    """Validación sobre residual GARCH **walk-forward** (point-in-time)."""
    fc = garch_forecast_vol_walkforward(
        df[close_col], horizon, refit_every=refit_every, min_train=min_train, window=window,
    )
    tmp = df[[regime_col, COHORT_COL]].copy()
    tmp["garch_resid"] = df[target_col] - fc
    return _kw_fdr_by_cohort(tmp, regime_col, "garch_resid", min_sample)
