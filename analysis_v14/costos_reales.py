"""Re-evaluación de trades V14 con costos reales de 6A (SPEC_COSTOS_6A). Uso: python analysis_v14/costos_reales.py <trades.csv>
No cambia QUÉ se opera: solo recalcula el costo. 6A: 1 pip (0.0001)=$10/contrato, tick (0.00005)=$5."""
import sys, numpy as np, pandas as pd

COMM_RT = 3.54          # $ por contrato ida y vuelta (usuario, Tradovate/Apex)
PIP_USD = 10.0
TICK_USD = 5.0
CONTRATOS = 6
RIESGO_MAX_USD = 500.0  # regla del usuario: nunca pierde más de ~$500 por trade con 6 contratos
CLEAN_FROM = pd.Timestamp("2026-01-01", tz="UTC")


def cost_r(t: pd.DataFrame, slip_ticks: float) -> pd.Series:
    risk_usd = t["risk_pips"] * PIP_USD                       # por contrato
    slip = np.where(t["outcome"] == "target", 0.0, slip_ticks * TICK_USD)   # entrada y TP a limit sin costo; stop/otras salidas pagan slippage
    return (COMM_RT + slip) / risk_usd


def stats(g: pd.DataFrame, c: pd.Series, seed=0) -> str:
    if len(g) == 0: return "n=0"
    net = (g["r_multiple"] - c.loc[g.index]).to_numpy()
    rng = np.random.default_rng(seed)
    bs = rng.choice(net, (5000, len(net))).mean(1) if len(net) > 1 else np.array([net.mean()])
    lo, hi = np.percentile(bs, [2.5, 97.5])
    return f"n={len(g):3d} win={np.mean(g['r_multiple']>0):.2f} bruto={g['r_multiple'].mean():+.3f}R costo={c.loc[g.index].mean():.3f}R neto={net.mean():+.3f}R IC95[{lo:+.2f},{hi:+.2f}]"


def main(path):
    t = pd.read_csv(path); t["entry_dt"] = pd.to_datetime(t["entry_time"], utc=True)
    print(f"outcomes: {t['outcome'].value_counts().to_dict()}")
    t["riesgo_usd_6c"] = t["risk_pips"] * PIP_USD * CONTRATOS
    sobre = t["riesgo_usd_6c"] > RIESGO_MAX_USD
    print(f"riesgo$ con 6 contratos: mediana {t.riesgo_usd_6c.median():.0f}  p90 {t.riesgo_usd_6c.quantile(.9):.0f}  max {t.riesgo_usd_6c.max():.0f}  |  ops > ${RIESGO_MAX_USD:.0f}: {sobre.sum()} de {len(t)} ({sobre.mean():.0%})")
    for slip in (0, 1, 2):
        c = cost_r(t, slip)
        print(f"\n=== slippage {slip} tick(s) en salidas por stop; modelo viejo costo medio {t['cost_r'].mean():.3f}R ===")
        for name, g in (("LIMPIA 2026+", t[t.entry_dt >= CLEAN_FROM]), ("DEV <2026 (descriptivo)", t[t.entry_dt < CLEAN_FROM]), ("TODO", t)):
            print(f"{name:24s}", stats(g, c))
        if slip == 1:
            for b, g in t.groupby("bucket"): print(f"  bucket {b:3s}   ", stats(g, c))
            print("  -- sensibilidad: solo trades con riesgo <= $500 (tu regla real) --")
            ok = t[~sobre]
            for name, g in (("LIMPIA 2026+", ok[ok.entry_dt >= CLEAN_FROM]), ("DEV <2026", ok[ok.entry_dt < CLEAN_FROM])):
                print(f"  {name:22s}", stats(g, c))
            for b, g in ok.groupby("bucket"): print(f"    bucket {b:3s} ", stats(g, c))


if __name__ == "__main__":
    main(sys.argv[1])
