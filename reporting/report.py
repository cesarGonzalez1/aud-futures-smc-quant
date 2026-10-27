"""Generación de reportes de estado de mercado on-demand (Fase 3, sección 8).

Traduce la salida de `analysis/` a un reporte Markdown legible que responde las 6
preguntas de la sección 8. NO genera señales de compra/venta.

Cifra de evidencia PRINCIPAL: el resultado GARCH **walk-forward** (el más riguroso
disponible). El in-sample se menciona solo como nota metodológica de contraste.

Advertencia de proxy (ADR-006) SIEMPRE visible: la estructura intradía viene del
proxy spot AUD/USD, no del futuro real 6A.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from analysis import regime as regime_mod
from analysis.cohorts import add_cohort
from analysis.run import PROXY_WARNING
from data import ingest, schema
from data.storage import parquet_store

WF_EXPERIMENT_GLOB = "*_regime_vs_garch_walkforward"


def current_state(df: pd.DataFrame) -> dict:
    """Estado de la última barra: régimen, sesión activa, indicadores clave."""
    last = df.iloc[-1]
    sessions = [c[3:] for c in df.columns if c.startswith("in_") and bool(last[c])]
    return {
        "timestamp": df.index[-1].isoformat(),
        "regime_trend": last.get(regime_mod.TREND_COL),
        "regime_vol": last.get(regime_mod.VOL_COL),
        "regime": last.get(regime_mod.REGIME_COL),
        "active_sessions": sessions,
        "close": float(last[schema.CLOSE]),
        "adx": float(last["adx"]),
        "atr": float(last["atr"]),
        "rsi": float(last["rsi"]),
        "above_ema_trend": bool(last[schema.CLOSE] > last["ema_trend"]),
    }


def recent_change(df: pd.DataFrame, lookback: int = 24) -> str:
    """Qué cambió: régimen actual vs. el de hace `lookback` barras."""
    if len(df) <= lookback:
        return "sin barra de referencia previa"
    now = df[regime_mod.REGIME_COL].iloc[-1]
    before = df[regime_mod.REGIME_COL].iloc[-1 - lookback]
    if now == before:
        return f"régimen estable en '{now}' durante las últimas {lookback} barras"
    return f"régimen cambió de '{before}' a '{now}' en las últimas {lookback} barras"


def structure_summary(df: pd.DataFrame, lookback: int = 200) -> dict:
    """Estructura reciente: conteo de sweeps y último swing/sweep en la ventana."""
    tail = df.tail(lookback)
    def _last_true(col):
        s = tail.index[tail[col]] if col in tail.columns else []
        return s[-1].isoformat() if len(s) else None
    return {
        "lookback": lookback,
        "sweeps_high": int(tail.get("liquidity_sweep_high", pd.Series(dtype=bool)).sum()),
        "sweeps_low": int(tail.get("liquidity_sweep_low", pd.Series(dtype=bool)).sum()),
        "last_sweep_high": _last_true("liquidity_sweep_high"),
        "last_sweep_low": _last_true("liquidity_sweep_low"),
    }


def load_walkforward_evidence(exp_dir: Path, regime_col: str = regime_mod.REGIME_COL) -> dict:
    """Resume el experimento walk-forward para el régimen dado."""
    data = json.loads((exp_dir / "results.json").read_text(encoding="utf-8"))
    wf = pd.DataFrame(data[regime_col]["walkforward"])
    sig = wf[wf["p_fdr"] < 0.05]
    return {
        "experiment": exp_dir.name,
        "n_cohorts": int(len(wf)),
        "n_significant": int(len(sig)),
        "p_fdr_max_sig": float(sig["p_fdr"].max()) if len(sig) else None,
        "epsilon2_min": float(wf["epsilon2"].min(skipna=True)),
        "epsilon2_max": float(wf["epsilon2"].max(skipna=True)),
    }


def _latest_wf_experiment(exp_base: Path) -> Path | None:
    dirs = sorted(exp_base.glob(WF_EXPERIMENT_GLOB))
    return dirs[-1] if dirs else None


def compose_report(state: dict, change: str, structure: dict, evidence: dict | None,
                   generated_at: str) -> str:
    """Arma el Markdown del reporte respondiendo las 6 preguntas de la sección 8."""
    ev_line = (
        f"El régimen aporta valor predictivo sobre la volatilidad futura por encima "
        f"de un baseline GARCH(1,1) **walk-forward** en {evidence['n_significant']}/"
        f"{evidence['n_cohorts']} cohortes (p_fdr ≤ {evidence['p_fdr_max_sig']:.1e}), "
        f"pero el **efecto es pequeño** (epsilon² {evidence['epsilon2_min']:.3f}–"
        f"{evidence['epsilon2_max']:.3f}). Fuente: `{evidence['experiment']}`."
        if evidence else "Sin experimento de evidencia disponible."
    )
    lines = [
        f"# Estado de mercado AUD/USD — {generated_at}",
        "",
        f"> ⚠️ {PROXY_WARNING}",
        "",
        "## 1. ¿Qué está pasando ahora?",
        f"- Barra: {state['timestamp']}  ·  close={state['close']:.5f}",
        f"- Régimen: **{state['regime']}** (tendencia={state['regime_trend']}, "
        f"volatilidad={state['regime_vol']})",
        f"- Sesión(es) activa(s): {', '.join(state['active_sessions']) or 'ninguna'}",
        f"- ADX={state['adx']:.1f}  ·  ATR={state['atr']:.5f}  ·  RSI={state['rsi']:.1f}  ·  "
        f"{'sobre' if state['above_ema_trend'] else 'bajo'} EMA(50)",
        "",
        "## 2. ¿Hay estructura de mercado relevante?",
        f"- En las últimas {structure['lookback']} barras: {structure['sweeps_high']} sweeps "
        f"de máximos, {structure['sweeps_low']} de mínimos.",
        f"- Último sweep de máximos: {structure['last_sweep_high'] or '—'}",
        f"- Último sweep de mínimos: {structure['last_sweep_low'] or '—'}",
        "",
        "## 3. ¿Qué evidencia lo respalda?",
        f"- {ev_line}",
        "",
        "## 4. ¿Qué tan confiable es, y en qué base?",
        "- Confianza estadística ALTA en que existe una relación régimen→volatilidad "
        "futura (sobrevive walk-forward, control FDR por cohorte).",
        "- Pero la MAGNITUD del efecto es pequeña: el régimen refina, no determina.",
        "- Nota metodológica: el baseline in-sample (más laxo) da efectos algo mayores; "
        "la cifra de referencia es la walk-forward por ser point-in-time.",
        "",
        "## 5. ¿Qué cambió respecto al período anterior?",
        f"- {change}",
        "",
        "## 6. ¿Qué vigilar a continuación?",
        "- Persistencia del régimen actual y su transición.",
        "- Sweeps recientes como posibles zonas de interés (contexto, no señal).",
        "- Recordatorio: lecturas sobre proxy spot; confirmar en el instrumento real 6A.",
        "",
        "_No se generan señales de compra/venta. Solo lecturas de contexto._",
    ]
    return "\n".join(lines)


def build_report(config: dict | None = None) -> Path:
    """Construye y guarda el reporte de estado de mercado. Devuelve su ruta."""
    config = config or ingest.load_config()
    feat_base = config["paths"]["features"]
    symbol = config["instruments"]["primary"]["symbol"]
    df = parquet_store.read_dataset(feat_base, symbol, "H1")
    df = add_cohort(df, mode=config["cohorts"]["mode"])
    df = regime_mod.add_regime(df)

    state = current_state(df)
    change = recent_change(df)
    structure = structure_summary(df)
    exp = _latest_wf_experiment(Path(config["paths"]["experiments"]))
    evidence = load_walkforward_evidence(exp) if exp else None

    ts = datetime.now(timezone.utc)
    md = compose_report(state, change, structure, evidence, ts.date().isoformat())

    out_dir = Path(config["paths"]["reports"])
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{ts.date().isoformat()}_market_state.md"
    out.write_text(md, encoding="utf-8")
    return out


def main() -> None:
    out = build_report()
    print(f"Reporte generado: {out}")
    print(out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
