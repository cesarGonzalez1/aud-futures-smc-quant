"""V13 = V12 con el bias del usuario codificado (SPEC_V13). Una corrida registrada. Uso: python -m backtest.run_v13"""
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
from strategy.v13_confluence import build_v13_confluence


def run(config=None):
    config = config or ingest.load_config()
    m5, h1, _old_conf, man, _ = _prepare(config, None)
    m5 = add_session_vwap(m5)
    conf = build_v13_confluence(m5, h1)
    # candle_aligned V13: dir(ayer)==dir(hoy) con hoy = última sesión completa (D1-B)
    day = m5.index.normalize()
    m5["prev_dir"] = pd.Series(day, index=m5.index).map(conf["dir_ayer"]).fillna(0).astype(int).to_numpy()
    m5["today_dir"] = pd.Series(day, index=m5.index).map(conf["dir_hoy"]).fillna(0).astype(int).to_numpy()
    half_spread = float(m5["spread"].dropna().mean()) / 2.0
    atr_ref = float(m5["atr"].dropna().median())
    t = generate_trades_v12(m5, h1, conf)
    if t.empty:
        return {"trades": t, "n_total": 0, "conf": conf, "dataset_sha256": man.sha256}
    t = metrics.apply_costs(t, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)
    t["entry_dt"] = pd.to_datetime(t["entry_time"], utc=True)
    t["perfecto"] = (t["bucket"] == "A") & t["candle_aligned"] & (t["trigger"] == "eq_vwap")
    return {"trades": t, "n_total": len(t), "validity": validity_label(len(t)), "conf": conf, "dataset_sha256": man.sha256}


def report(p):
    t = p["trades"]; c = p["conf"]
    out = [f"# V13 — {datetime.now(timezone.utc).date()}", f"> {EXPLORATORY_NOTE}", "",
           f"**{p['n_total']} ops** → {p['validity']}. Días con bias 'alta': {(c.confidence=='alta').mean():.1%} de {len(c)} (V12: 9%).", "",
           "## Primaria A>B+C", primary_test(t), "", "## Global", repr(cell(t)), ""]
    for name, d in (("TODO", t), ("SIN 2024 (calibración)", t[t.entry_dt.dt.year != 2024])):
        out += [f"## {name} n={len(d)}", repr(cell(d)), table(d, "bucket").to_string(), table(d, "trigger").to_string(),
                table(d, "candle_aligned").to_string(), ""]
    out += ["## Por año", table(t, "cohort").to_string()]
    return "\n".join(out)


def main():
    config = ingest.load_config(); p = run(config)
    if not p["n_total"]:
        print("V13: 0 operaciones"); return
    exp = Path(config["paths"]["experiments"]) / f"{datetime.now(timezone.utc).date()}_strat_v13_bias_usuario"
    exp.mkdir(parents=True, exist_ok=True)
    p["trades"].drop(columns=["entry_dt"]).to_csv(exp / "trades.csv", index=False)
    p["conf"].to_csv(exp / "confluence.csv")
    txt = report(p); (exp / "report.md").write_text(txt, encoding="utf-8"); print(txt); print("Guardado en:", exp)

if __name__ == "__main__":
    main()
