"""Sensibilidad PREDEFINIDA de SPEC_V17 (no implementada en run_v17): excluir sesiones con roll de contrato.
Lee trades.csv de la corrida V17 (no re-corre nada). Uso: python analysis_v16/v17_sin_rolls.py [carpeta_experimento]"""
import sys, pandas as pd
sys.path.insert(0, ".")
from analysis_v14.costos_reales import cost_r, stats
exp = sys.argv[1] if len(sys.argv) > 1 else "experiments/2026-11-15_strat_v17_6a_real"
t = pd.read_csv(f"{exp}/trades.csv"); t["entry_dt"] = pd.to_datetime(t["entry_time"], utc=True)
m5 = pd.read_parquet("data/raw/6A/M5/data.parquet", columns=["instrument_id"])
rolls = set(m5.index[m5.instrument_id.ne(m5.instrument_id.shift())][1:].normalize())
t["dia"] = t.entry_dt.dt.normalize()
for slip in (1,):
    c = cost_r(t, slip)
    print(f"TODAS      ({len(t)}):", stats(t, c))
    k = t[~t["dia"].isin(rolls)]
    print(f"SIN ROLLS  ({len(k)}):", stats(k, c))
    print(f"SOLO ROLLS ({len(t) - len(k)}): ", stats(t[t['dia'].isin(rolls)], c) if len(t) - len(k) else "n=0")
