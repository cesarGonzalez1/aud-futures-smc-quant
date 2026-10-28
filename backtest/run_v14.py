"""V14 = V13 con NY PM como información (SPEC_V14). Una corrida registrada. Uso: python -m backtest.run_v14"""
from __future__ import annotations
from datetime import datetime, timezone
from pathlib import Path
import numpy as np, pandas as pd
from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import validity_label
from backtest.run_v5 import _prepare
from backtest.run_v12 import cell, table, primary_test
from data import ingest
from features.vwap import add_session_vwap
from strategy.liquidity_sweep_ifvg_v12 import generate_trades_v12
from strategy.v14_confluence import build_v14_confluence

CLEAN_FROM = pd.Timestamp("2026-01-01", tz="UTC")   # SPEC_V14: prueba limpia


def run(config=None):
    config = config or ingest.load_config()
    m5, h1, _old, man, _ = _prepare(config, None)
    m5 = add_session_vwap(m5)
    conf = build_v14_confluence(m5, h1)
    day = pd.Series(m5.index.normalize(), index=m5.index)
    m5["prev_dir"] = day.map(conf["dir_ayer"]).fillna(0).astype(int).to_numpy()
    m5["today_dir"] = day.map(conf["dir_hoy"]).fillna(0).astype(int).to_numpy()
    half_spread = float(m5["spread"].dropna().mean()) / 2.0
    atr_ref = float(m5["atr"].dropna().median())
    t = generate_trades_v12(m5, h1, conf)
    if t.empty:
        return {"trades": t, "n_total": 0, "conf": conf, "dataset_sha256": man.sha256}
    t = metrics.apply_costs(t, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)
    t["entry_dt"] = pd.to_datetime(t["entry_time"], utc=True)
    pm = conf["ny_pm"].reindex(t["entry_dt"].dt.normalize()).to_numpy()
    want = np.where(t["side"] == "long", 1, -1)
    t["pm_rel"] = np.select([pm == want, pm == 0], ["a_favor", "neutral"], default="en_contra")
    t["perfecto"] = (t["bucket"] == "A") & t["candle_aligned"] & (t["trigger"] == "eq_vwap")
    return {"trades": t, "n_total": len(t), "validity": validity_label(len(t)), "conf": conf, "dataset_sha256": man.sha256}


def report(p):
    t = p["trades"]; c = p["conf"]
    clean = t[t.entry_dt >= CLEAN_FROM]; dev = t[t.entry_dt < CLEAN_FROM]
    out = [f"# V14 — {datetime.now(timezone.utc).date()}", f"> {EXPLORATORY_NOTE}", "",
           f"**{p['n_total']} ops** (dev {len(dev)}, limpia 2026+ {len(clean)}). Días con puerta abierta: {(c.confidence=='alta').mean():.1%} de {len(c)}.", "",
           f"## PRIMARIA (limpia, entrada >= 2026-01-01) n={len(clean)} → {validity_label(len(clean))}", primary_test(clean) if len(clean) else "sin operaciones",
           repr(cell(clean)) if len(clean) else ""]
    if len(clean):
        for col in ("bucket", "pm_rel", "trigger", "candle_aligned"):
            out += [f"### por {col}", table(clean, col).to_string(), ""]
    out += ["", f"## DESCRIPTIVA (dev, < 2026) n={len(dev)} — V13 ya vio estos datos; no es prueba", repr(cell(dev)) if len(dev) else "-"]
    if len(dev):
        for col in ("bucket", "pm_rel"):
            out += [f"### por {col}", table(dev, col).to_string(), ""]
    out += ["## Por año", table(t, "cohort").to_string()]
    return "\n".join(out)


def main():
    config = ingest.load_config(); p = run(config)
    if not p["n_total"]:
        print("V14: 0 operaciones"); return
    exp = Path(config["paths"]["experiments"]) / f"{datetime.now(timezone.utc).date()}_strat_v14_pm_informativo"
    exp.mkdir(parents=True, exist_ok=True)
    p["trades"].drop(columns=["entry_dt"]).to_csv(exp / "trades.csv", index=False)
    p["conf"].to_csv(exp / "confluence.csv")
    txt = report(p); (exp / "report.md").write_text(txt, encoding="utf-8"); print(txt); print("Guardado en:", exp)

if __name__ == "__main__":
    main()
