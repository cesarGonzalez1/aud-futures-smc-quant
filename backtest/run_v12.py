"""Backtest V12 ("trade de cajón") + efectividad por tipo de setup. Ver SPEC_V12.md.

Una sola corrida registrada. Hipótesis primaria: expectancy(bucket A) > expectancy(B + C).
Todo lo demás es descriptivo. n<30 por celda => inconcluso (ADR-009).

Uso:  python -m backtest.run_v12
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from backtest import metrics
from backtest.run import EXPLORATORY_NOTE
from backtest.run_v3 import validity_label
from backtest.run_v5 import _prepare
from data import ingest
from features.daily_candle import add_trading_day_candle
from features.vwap import add_session_vwap
from strategy.liquidity_sweep_ifvg_v12 import generate_trades_v12

MIN_N = 30
SPLIT = pd.Timestamp("2024-01-01", tz="UTC")
RNG = np.random.default_rng(12)   # semilla fija: reproducible


def _boot_ci(x: np.ndarray, n: int = 5000) -> tuple[float, float]:
    if len(x) < 2:
        return (np.nan, np.nan)
    m = RNG.choice(x, size=(n, len(x)), replace=True).mean(axis=1)
    return float(np.percentile(m, 2.5)), float(np.percentile(m, 97.5))


def cell(df: pd.DataFrame) -> dict:
    n = len(df)
    if n == 0:
        return dict(n=0)
    net, gross = df["r_net"].to_numpy(), df["r_multiple"].to_numpy()
    lo, hi = _boot_ci(net)
    return dict(
        n=n, win=round(float((net > 0).mean()), 3), exp_net=round(float(net.mean()), 3),
        ic95=f"[{lo:+.2f},{hi:+.2f}]", exp_bruta=round(float(gross.mean()), 3),
        costo_R=round(float(df["cost_r"].mean()), 3),
        avg_win=round(float(net[net > 0].mean()), 3) if (net > 0).any() else np.nan,
        avg_loss=round(float(net[net <= 0].mean()), 3) if (net <= 0).any() else np.nan,
        veredicto="inconcluso (n<30)" if n < MIN_N else ("IC>0" if lo > 0 else ("IC<0" if hi < 0 else "IC cruza 0")),
    )


def table(df: pd.DataFrame, by: str) -> pd.DataFrame:
    rows = {k: cell(g) for k, g in df.groupby(by, dropna=False, sort=True)}
    return pd.DataFrame(rows).T


def run(config: dict | None = None) -> dict:
    config = config or ingest.load_config()
    m5, h1, confluence, man, _ = _prepare(config, None)
    m5 = add_session_vwap(m5)
    m5 = add_trading_day_candle(m5)

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    t = generate_trades_v12(m5, h1, confluence)
    if t.empty:
        return {"trades": t, "n_total": 0, "dataset_sha256": man.sha256}
    t = metrics.apply_costs(t, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)
    t["entry_dt"] = pd.to_datetime(t["entry_time"], utc=True)
    t["split"] = np.where(t["entry_dt"] < SPLIT, "train_2020-23", "test_2024-25")
    t["perfecto"] = (t["bucket"] == "A") & t["candle_aligned"] & (t["trigger"] == "eq_vwap")
    t["profundidad"] = pd.qcut(t["sweep_depth_atr"], 3, labels=["baja", "media", "alta"], duplicates="drop")
    return {"trades": t, "n_total": len(t), "validity": validity_label(len(t)),
            "half_spread": half_spread, "atr_ref": atr_ref, "dataset_sha256": man.sha256}


def primary_test(t: pd.DataFrame) -> str:
    a = t.loc[t["bucket"] == "A", "r_net"].to_numpy()
    bc = t.loc[t["bucket"].isin(["B", "C"]), "r_net"].to_numpy()
    if len(a) < 2 or len(bc) < 2:
        return "no evaluable (falta muestra en A o B+C)"
    diffs = (RNG.choice(a, (5000, len(a))).mean(1) - RNG.choice(bc, (5000, len(bc))).mean(1))
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return (f"exp(A)={a.mean():+.3f}R (n={len(a)}) vs exp(B+C)={bc.mean():+.3f}R (n={len(bc)}); "
            f"dif={a.mean() - bc.mean():+.3f}R, IC95 dif [{lo:+.2f},{hi:+.2f}] "
            f"{'-> A mejor (IC>0)' if lo > 0 else '-> NO se confirma A > B+C'}")


def report(p: dict) -> str:
    t = p["trades"]
    out = [f"# V12 — efectividad por setup — {datetime.now(timezone.utc).date()}", "",
           f"> {EXPLORATORY_NOTE}", "", f"**{p['n_total']} operaciones** → {p['validity']} (ADR-009). Una corrida registrada.", "",
           "## Hipótesis primaria (fijada antes)", primary_test(t), "",
           "## Global", cell(t).__repr__(), ""]
    for split, g in t.groupby("split"):
        out += [f"## Bucket horario — {split}", table(g, "bucket").to_string(), ""]
    out += ["## Bucket horario — TODO", table(t, "bucket").to_string(), "",
            "## Tipo de disparador", table(t, "trigger").to_string(), "",
            "## Vela previa == hoy == dirección (candle_aligned)", table(t, "candle_aligned").to_string(), "",
            "## n alineadas (3 ó 4 de 4)", table(t, "n_aligned").to_string(), "",
            "## Profundidad del sweep (terciles, descriptivo)", table(t, "profundidad").to_string(), "",
            "## PERFECTO (A ∧ vela alineada ∧ eq_vwap) vs resto", table(t, "perfecto").to_string(), "",
            "## Por cohorte (año)", table(t, "cohort").to_string(), "",
            "## Zona usada para TP", table(t, "zone").to_string(), ""]
    return "\n".join(out)


def main() -> None:
    config = ingest.load_config()
    p = run(config)
    if not p["n_total"]:
        print("V12: 0 operaciones"); return
    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_strat_v12_trade_cajon"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "config.yaml").write_text(
        "objetivo: V12 trade de cajon del usuario (SPEC_V12.md, fijada antes de correr)\n"
        f"dataset_sha256: {p['dataset_sha256']}\nn_total: {p['n_total']}\n"
        "tests_multiples: corrida unica registrada (+1). Cambiar horas/bandas/RR tras ver resultado activa 6.2\n"
        f"nota: \"{EXPLORATORY_NOTE}\"\n", encoding="utf-8")
    p["trades"].drop(columns=["entry_dt"]).to_csv(exp / "trades.csv", index=False)
    txt = report(p)
    (exp / "report.md").write_text(txt, encoding="utf-8")
    print(txt)
    print(f"\nGuardado en: {exp}")


if __name__ == "__main__":
    main()
