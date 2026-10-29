"""Calibración de V16 por REPRODUCCIÓN del ledger (SPEC_V16 §3). Uso: python analysis_v16/reproducir_ledger.py <journal_ledger.csv> <año>
Para cada trade del ledger se fuerza el LADO del usuario (aísla la mecánica de entrada del bias) y se pregunta si el motor
encuentra la misma entrada ese día: mismo día de sesión, entrada y SL dentro de TOL_PIPS. NO mira P&L."""
import sys, itertools, numpy as np, pandas as pd
sys.path.insert(0, ".")
from backtest.run_v5 import _prepare
from data import ingest
from features.vwap import add_session_vwap
from strategy.liquidity_sweep_ifvg_v16 import generate_trades_v16, with_sweep_lookback, TICK_6A

TOL_PIPS = 3.0
ledger_path, year = sys.argv[1], int(sys.argv[2])
config = ingest.load_config()
m5, h1, _old, man, _ = _prepare(config, None)
m5 = add_session_vwap(m5)

L = pd.read_csv(ledger_path, parse_dates=["fecha"]); L = L[L.fecha.dt.year == year].copy()
def sdate(d):
    s = d + pd.Timedelta(days=1)
    return d if s.weekday() == 5 else s              # SPEC_V13 §2: D+1 sábado -> sesión de D
L["sesion"] = L.fecha.map(sdate).dt.tz_localize("UTC")
L = L[(L.sesion.dt.weekday != 6) & (L.sesion <= m5.index.max())].drop_duplicates("sesion").reset_index(drop=True)
conf = pd.DataFrame({"direction": np.where(L.lado == "Long", 1, -1), "confidence": "alta", "d1": 0, "h4": 0, "ny_am": 0, "ny_pm": 0}, index=pd.DatetimeIndex(L.sesion))

rows = []
for lookback in (50, 222):
    mm = with_sweep_lookback(m5, lookback)
    for confirm, gate, tick, rr in itertools.product(("ifvg", "first"), (True, False), (0.0, TICK_6A), ("zones", "fixed")):
        t = generate_trades_v16(mm, h1, conf, confirm=confirm, trigger_gate=gate, sl_tick=tick, rr_mode=rr)
        t["sesion"] = pd.to_datetime(t["entry_time"], utc=True).dt.normalize() if len(t) else pd.NaT
        m = L.merge(t, on="sesion", how="left", suffixes=("", "_m")) if len(t) else L.assign(entry_price=np.nan, stop=np.nan, target=np.nan)
        e = (m["entry_price"] - m["entry"]).abs() * 1e4; s = (m["stop"] - m["sl"]).abs() * 1e4; tp = (m["target"] - m["tp"]).abs() * 1e4
        found = m["entry_price"].notna()
        rows.append(dict(lookback=lookback, confirm=confirm, trigger_gate=gate, sl_tick=tick, rr_mode=rr, n_ledger=len(L),
                         encuentra=round(found.mean(), 3), entrada_ok=round((found & (e <= TOL_PIPS)).mean(), 3),
                         sl_ok=round((found & (s <= TOL_PIPS)).mean(), 3), completo=round((found & (e <= TOL_PIPS) & (s <= TOL_PIPS)).mean(), 3),
                         tp_ok=round((found & (e <= TOL_PIPS) & (s <= TOL_PIPS) & (tp <= TOL_PIPS)).mean(), 3),
                         mediana_dif_entrada=round(float(e[found].median()), 2) if found.any() else np.nan,
                         mediana_dif_sl=round(float(s[found].median()), 2) if found.any() else np.nan))
res = pd.DataFrame(rows).sort_values(["completo", "encuentra"], ascending=False)
pd.set_option("display.width", 250); print(res.to_string(index=False))
res.to_csv(f"analysis_v16/reproduccion_{year}.csv", index=False)
base = res[(res.lookback == 50) & (res.confirm == "ifvg") & res.trigger_gate & (res.sl_tick == 0) & (res.rr_mode == "zones")].iloc[0]
print(f"\nBASELINE V15-mecánica (condicionada al lado del usuario): encuentra {base.encuentra:.0%}, completo {base.completo:.0%}")
