"""Backtest V4 (ADR-010) — señal V3 (M5) + stop en swing H1. EXPLORATORIO.

Mecánica idéntica a V3; único cambio: stop = swing H1 del lado barrido (mapeado
point-in-time a M5 vía merge_asof backward). Mismo protocolo de costos y métricas
por cohorte. Guarda `experiments/<fecha>_strat_liq_sweep_amd_v4/` sin tocar V1-V3.

Uso:
  python -m backtest.run_v4              # 5 años completos
  python -m backtest.run_v4 --months 3   # ventana corta (humo)
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
from features import indicators, levels, sessions, structure
from features.fvg import add_fvg_features
from strategy import liquidity_sweep_ifvg_v4 as v4


def _map_h1_swings_to_m5(m5: pd.DataFrame, h1: pd.DataFrame) -> pd.DataFrame:
    """Añade a M5 el último swing H1 confirmado ≤ t (point-in-time, merge_asof)."""
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

    d1 = parquet_store.read_dataset(raw, sym, "D1")
    d1 = indicators.add_trend_momentum(d1)
    bias = v4.daily_bias_from_d1(d1)

    h1 = parquet_store.read_dataset(raw, sym, "H1")
    h1 = structure.add_structure(h1)            # swings H1 (para el stop)

    m5 = parquet_store.read_dataset(raw, sym, "M5")
    if months is not None:
        cutoff = m5.index[0] + pd.DateOffset(months=months)
        m5 = m5[m5.index < cutoff]
        h1 = h1[h1.index < cutoff]
    m5 = indicators.add_trend_momentum(m5)
    m5 = indicators.add_volatility(m5)
    m5 = regime_mod.add_regime(m5)
    m5 = sessions.add_sessions(m5, config["sessions"])
    m5 = structure.add_structure(m5)
    m5 = structure.add_order_blocks(m5)
    m5 = levels.add_pdh_pdl(m5, d1)
    m5 = levels.add_pwh_pwl(m5, d1)
    m5 = levels.add_tokyo_session_levels(m5)
    m5 = levels.add_equal_levels(m5)
    m5 = levels.add_accumulation_range(m5, window=config.get("v2", {}).get("acc_window", 6))
    m5 = add_fvg_features(m5, min_atr_frac=0.1)
    m5 = _map_h1_swings_to_m5(m5, h1)           # stop = swing H1 (ADR-010)

    man = read_manifest(parquet_store.dataset_dir(raw, sym, "M5"))
    return m5, bias, man


def run(config: dict | None = None, months: int | None = None) -> dict:
    config = config or ingest.load_config()
    m5, bias, man = _prepare(config, months)

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    trades = v4.generate_trades_v4(m5, bias)
    pois = getattr(v4.generate_trades_v4, "_last_pois", None)
    t4 = v4.trades_to_frame(trades, pois)
    t4 = metrics.apply_costs(t4, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)

    return {
        "trades": t4, "net": metrics.metrics_by_cohort(t4, r_col="r_net"),
        "n_total": len(t4), "validity": validity_label(len(t4)),
        "half_spread": half_spread, "atr_ref": atr_ref,
        "dataset_sha256": man.sha256, "role": man.role, "months": months,
    }


def _write_experiment(payload: dict, config: dict) -> Path:
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_liq_sweep_amd_v4"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: backtest exploratorio V4 (senal V3 + stop en swing H1, ADR-010)\n"
        f"dataset_sha256: {payload['dataset_sha256']}\n"
        f"role: {payload['role']}\n"
        f"n_total: {payload['n_total']}\n"
        f"window_months: {payload['months']}\n"
        f"validity_gate: \"{payload['validity']}\"\n"
        f"half_spread: {payload['half_spread']:.6f}\n"
        f"atr_ref: {payload['atr_ref']:.6f}\n"
        "deflated_sharpe: no aplica (una hipotesis predefinida, ADR-010)\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n", encoding="utf-8")
    payload["trades"].to_json(exp / "results.json", orient="records", indent=2, date_format="iso")
    lines = [f"# Backtest V4 (señal V3 + stop swing H1, ADR-010) — {ts.date().isoformat()}",
             "", f"> {EXPLORATORY_NOTE}", "",
             f"## Gate (ADR-009): **{payload['n_total']} ops → {payload['validity']}**", "",
             "## V4 NETO por cohorte", payload["net"].to_string(index=False)]
    (exp / "report.md").write_text("\n".join(lines), encoding="utf-8")
    return exp


def main() -> None:
    months = None
    if "--months" in sys.argv:
        months = int(sys.argv[sys.argv.index("--months") + 1])
    config = ingest.load_config()
    payload = run(config, months=months)
    tag = f" (ventana {months} meses)" if months else " (5 años)"
    print(f"=== Backtest V4 (señal V3 + stop swing H1, ADR-010){tag} — EXPLORATORIO ===")
    print(f"GATE: {payload['n_total']} operaciones → {payload['validity']}")
    exp = _write_experiment(payload, config)
    print(f"Experimento guardado en: {exp}")


if __name__ == "__main__":
    main()
