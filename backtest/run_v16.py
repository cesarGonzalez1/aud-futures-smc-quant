"""V16 = mecánica del usuario (SPEC_V16) con la puerta de V15. Una corrida registrada. Uso: python -m backtest.run_v16"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd
from analysis_v14.costos_reales import cost_r as cost_real, CONTRATOS, PIP_USD, RIESGO_MAX_USD
from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import validity_label
from backtest.run_v5 import _prepare
from backtest.run_v12 import cell, table, primary_test
from data import ingest
from features.vwap import add_session_vwap
from strategy.liquidity_sweep_ifvg_v16 import generate_trades_v16
from strategy.v15_confluence import build_v15_confluence

SPLIT = pd.Timestamp("2026-01-01", tz="UTC")


def run(config=None):
    config = config or ingest.load_config()
    m5, h1, _old, man, _ = _prepare(config, None)
    m5 = add_session_vwap(m5)
    conf = build_v15_confluence(m5, h1)
    day = pd.Series(m5.index.normalize(), index=m5.index)
    m5["prev_dir"] = day.map(conf["dir_ayer"]).fillna(0).astype(int).to_numpy()
    m5["today_dir"] = day.map(conf["dir_hoy"]).fillna(0).astype(int).to_numpy()
    half_spread = float(m5["spread"].dropna().mean()) / 2.0
    atr_ref = float(m5["atr"].dropna().median())
    t = generate_trades_v16(m5, h1, conf)
    if t.empty:
        return {"trades": t, "n_total": 0, "conf": conf, "dataset_sha256": man.sha256}
    t = metrics.apply_costs(t, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)
    t["entry_dt"] = pd.to_datetime(t["entry_time"], utc=True)
    d = t["entry_dt"].dt.normalize()
    pm = conf["ny_pm"].reindex(d).to_numpy(); want = np.where(t["side"] == "long", 1, -1)
    t["pm_rel"] = np.select([pm == want, pm == 0], ["a_favor", "neutral"], default="en_contra")
    t["gate_tipo"] = conf["gate_tipo"].reindex(d).to_numpy()
    t["riesgo_usd_6c"] = t["risk_pips"] * PIP_USD * CONTRATOS
    t["perfecto"] = (t["bucket"] == "A") & t["candle_aligned"] & (t["trigger"] == "eq_vwap")
    return {"trades": t, "n_total": len(t), "validity": validity_label(len(t)), "conf": conf, "dataset_sha256": man.sha256}


def _real(t: pd.DataFrame, slip: float) -> pd.DataFrame:
    """Mismo conjunto de operaciones con costo real 6A (SPEC_COSTOS_6A): r_net y cost_r reemplazados."""
    r = t.copy(); r["cost_r"] = cost_real(r, slip); r["r_net"] = r["r_multiple"] - r["cost_r"]
    return r


def report(p):
    t = p["trades"]; c = p["conf"]; r1 = _real(t, 1)
    out = [f"# V16 — {datetime.now(timezone.utc).date()}", f"> {EXPLORATORY_NOTE}", "",
           f"**{p['n_total']} ops** → {p['validity']}. Días con puerta abierta: {(c.confidence=='alta').mean():.1%} de {len(c)} (V15: 43.1%).", "",
           "## PRIMARIA (todas las entradas, costo REAL 6A, 1 tick en stops)", primary_test(r1), repr(cell(r1)), ""]
    for slip in (0, 2):
        out += [f"### sensibilidad slippage {slip} tick(s): " + repr(cell(_real(t, slip)))]
    out += ["", "## Con costo del modelo viejo (referencia)", primary_test(t), repr(cell(t)), ""]
    for name, d in (("2026+", r1[r1.entry_dt >= SPLIT]), ("< 2026", r1[r1.entry_dt < SPLIT])):
        out += [f"## {name} (costo real 1 tick) n={len(d)}", repr(cell(d)) if len(d) else "-"]
    for col in ("bucket", "confirm_type", "gate_tipo", "pm_rel", "trigger", "candle_aligned"):
        out += ["", f"### por {col} (costo real 1 tick)", table(r1, col).to_string()]
    ok = r1[r1["riesgo_usd_6c"] <= RIESGO_MAX_USD]
    out += ["", f"## Sensibilidad: solo riesgo <= ${RIESGO_MAX_USD:.0f} con {CONTRATOS} contratos n={len(ok)} de {len(r1)}", repr(cell(ok)) if len(ok) else "-",
            table(ok, "bucket").to_string() if len(ok) else "", "", "## Por año (costo real 1 tick)", table(r1, "cohort").to_string()]
    return "\n".join(out)


def main():
    config = ingest.load_config(); p = run(config)
    if not p["n_total"]:
        print("V16: 0 operaciones"); return
    exp = Path(config["paths"]["experiments"]) / f"{datetime.now(timezone.utc).date()}_strat_v16_mecanica_usuario"
    exp.mkdir(parents=True, exist_ok=True)
    p["trades"].drop(columns=["entry_dt"]).to_csv(exp / "trades.csv", index=False)
    p["conf"].to_csv(exp / "confluence.csv")
    txt = report(p); (exp / "report.md").write_text(txt, encoding="utf-8"); print(txt); print("Guardado en:", exp)

if __name__ == "__main__":
    main()
