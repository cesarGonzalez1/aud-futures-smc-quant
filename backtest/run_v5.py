"""Backtest V5 (ADR-011) — bias de confluencia multi-timeframe + equal highs/lows
+ salida jerárquica "próximo punto de liquidez". EXPLORATORIO.

Mecánica de entrada (sweep + IFVG M5) heredada de V3; stop heredado de V4 (swing
H1, ver nota en `strategy/liquidity_sweep_ifvg_v5.py`). Lo nuevo: bias por
confluencia de 4 fuentes de estructura (D1, H4, sesión NY AM, sesión NY PM) en vez
del régimen D1, POI acotado a equal highs/lows "recientes" (desde 22:00 UTC), y
target jerárquico en vez de swing opuesto fijo.

Mismo protocolo de costos (medio spread M5 + slippage ATR) y métricas por cohorte
que V1-V4. Guarda `experiments/<fecha>_strat_liq_sweep_confluence_v5/` sin tocar
V1-V4.

Uso:
  python -m backtest.run_v5              # 5 años completos
  python -m backtest.run_v5 --months 3   # ventana corta (humo)
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from analysis import regime as regime_mod
from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import validity_label
from data import ingest, schema
from data.storage import parquet_store
from data.storage.manifest import read_manifest
from features import bias as bias_mod
from features import indicators, levels, sessions, structure
from features.fvg import add_fvg_features
from strategy import liquidity_sweep_ifvg_v5 as v5


def _map_h1_swings_to_m5(m5: pd.DataFrame, h1: pd.DataFrame) -> pd.DataFrame:
    """Añade a M5 el último swing H1 confirmado ≤ t (point-in-time). Idéntico al
    helper de `backtest/run_v4.py` (stop = swing H1, ver ADR-010/011)."""
    right = h1[["last_swing_high", "last_swing_low"]].rename(
        columns={"last_swing_high": "h1_swing_high", "last_swing_low": "h1_swing_low"}
    ).sort_index()
    right.index = right.index.rename("_rkey")
    left = m5.sort_index().reset_index()
    rr = right.reset_index()
    rr["_rkey"] = rr["_rkey"].astype(left[m5.index.name].dtype)
    merged = pd.merge_asof(left, rr, left_on=m5.index.name, right_on="_rkey",
                           direction="backward").set_index(m5.index.name).drop(columns=["_rkey"])
    return merged


def _prepare(config: dict, months: int | None):
    raw = config["paths"]["raw"]
    sym = config["instruments"]["primary"]["symbol"]
    cw = config.get("confluence_windows", {})
    ny_am = (cw.get("ny_am", {}).get("start_hour_utc", 12), cw.get("ny_am", {}).get("end_hour_utc", 15))
    ny_pm = (cw.get("ny_pm", {}).get("start_hour_utc", 19), cw.get("ny_pm", {}).get("end_hour_utc", 22))
    eq_window_start = cw.get("eq_poi_window_start_hour_utc", 22)
    entry_start = cw.get("entry_session", {}).get("start_hour_utc", 0)
    entry_end = cw.get("entry_session", {}).get("end_hour_utc", 4)

    d1 = parquet_store.read_dataset(raw, sym, "D1")

    h1 = parquet_store.read_dataset(raw, sym, "H1")
    m5 = parquet_store.read_dataset(raw, sym, "M5")
    if months is not None:
        cutoff = m5.index[0] + pd.DateOffset(months=months)
        m5 = m5[m5.index < cutoff]
        h1 = h1[h1.index < cutoff]
        d1 = d1[d1.index < cutoff]

    # --- H1: estructura (para bias H4/D1 vía resample y para el stop) + FVG (target) ---
    h1 = structure.add_structure(h1)
    h1 = indicators.add_volatility(h1)          # atr, para el filtro de tamaño de FVG
    h1 = add_fvg_features(h1, min_atr_frac=0.1)  # FVG en H1 (prioridad 1 de la salida, ADR-011)

    # --- D1: estructura (para bias D1) ---
    d1 = structure.add_structure(d1, k=2)

    # --- M5: toda la mecánica (igual que V3/V4) + piezas nuevas de V5 ---
    m5 = indicators.add_trend_momentum(m5)
    m5 = indicators.add_volatility(m5)
    m5 = regime_mod.add_regime(m5)               # regime_vol (prioridad 2 de la salida)
    m5 = sessions.add_sessions(m5, config["sessions"])
    m5 = structure.add_structure(m5)
    m5 = levels.add_pdh_pdl(m5, d1)
    m5 = levels.add_tokyo_session_levels(m5)
    m5 = levels.add_equal_levels(m5)
    m5 = levels.add_recent_equal_flag(
        m5, window_start_hour_utc=eq_window_start, entry_session_end_hour_utc=entry_end,
    )
    m5 = levels.add_day_extremes(m5)
    m5 = add_fvg_features(m5, min_atr_frac=0.1)   # IFVG de confirmación (M5, igual V3/V4)
    m5 = _map_h1_swings_to_m5(m5, h1)             # h1_swing_high/low (stop, igual V4)

    # --- Bias de confluencia (ADR-011): D1 + H4 + NY AM + NY PM ---
    confluence = bias_mod.build_daily_confluence(d1, h1, m5, ny_am_hours=ny_am, ny_pm_hours=ny_pm)

    man = read_manifest(parquet_store.dataset_dir(raw, sym, "M5"))
    return m5, h1, confluence, man, (entry_start, entry_end)


def run(config: dict | None = None, months: int | None = None) -> dict:
    config = config or ingest.load_config()
    m5, h1, confluence, man, (window_start, window_end) = _prepare(config, months)

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    trades, confidences, sources = v5.generate_trades_v5(
        m5, h1, confluence, window_start=window_start, window_end=window_end,
    )
    t5 = v5.trades_to_frame(trades, confidences, sources)
    t5 = metrics.apply_costs(t5, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)

    return {
        "trades": t5, "net": metrics.metrics_by_cohort(t5, r_col="r_net"),
        "n_total": len(t5), "validity": validity_label(len(t5)),
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": man.sha256, "role": man.role, "months": months,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_confluence_v5"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio V5 (confluencia multi-timeframe + equal highs/lows "
        "+ salida jerarquica, ADR-011)\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"n_total: {payload['n_total']}\n"
        f"window_months: {payload['months']}\n"
        f"validity_gate: \"{payload['validity']}\"\n"
        f"half_spread: {payload['half_spread']:.6f}\n"
        f"atr_ref: {payload['atr_ref']:.6f}\n"
        "deflated_sharpe: no aplica (una hipotesis predefinida, ADR-011)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n", encoding="utf-8")
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [f"# Backtest V5 (confluencia + equal highs/lows + salida jerárquica, ADR-011) — {ts.date().isoformat()}",
             "", f"> {EXPLORATORY_NOTE}", "",
             f"## Gate (ADR-009): **{payload['n_total']} ops → {payload['validity']}**", "",
             "## V5 NETO por cohorte", payload["net"].to_string(index=False)]
    if "confidence" in payload["trades"].columns and not payload["trades"].empty:
        lines += ["", "## V5 — operaciones por nivel de confianza (confluencia)",
                  payload["trades"]["confidence"].value_counts().to_string()]
    if "target_source" in payload["trades"].columns and not payload["trades"].empty:
        lines += ["", "## V5 — operaciones por fuente de target",
                  payload["trades"]["target_source"].value_counts().to_string()]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    months = None
    if "--months" in sys.argv:
        months = int(sys.argv[sys.argv.index("--months") + 1])
    config = ingest.load_config()
    payload = run(config, months=months)
    tag = f" (ventana {months} meses)" if months else " (5 años)"
    print(f"=== Backtest V5 (confluencia + equal highs/lows + salida jerárquica, ADR-011){tag} — EXPLORATORIO ===")
    print(f"GATE: {payload['n_total']} operaciones → {payload['validity']}")
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
