"""Calibración por ACUERDO de los candidatos de bias (SPEC_V13 §4). Uso: python analysis_v13/calibrar_bias.py <export_notion_all.csv> [año]"""
import sys, glob, numpy as np, pandas as pd
sys.path.insert(0, '.')
from data import ingest
from data.storage import parquet_store
from features.bias_user import compute_votes

notion, year = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 2024
cfg = ingest.load_config(); raw = cfg['paths']['raw']
m5 = parquet_store.read_dataset(raw, 'AUDUSD', 'M5'); h1 = parquet_store.read_dataset(raw, 'AUDUSD', 'H1')
d = pd.read_csv(notion); d['dia'] = pd.to_datetime(d['Dia del testing'], errors='coerce')
d = d[d.dia.dt.year == year].copy()
mp = {'Alcista': 1, 'Bajista': -1, 'Acumulativa': 0, 'Lateral': 0}
for k, c in (('d1', 'BIAS HTF D'), ('h4', 'BIAS HTF 4H'), ('am', 'BIAS NY AM'), ('pm', 'BIAS NY PM')):
    d[k] = d[c].map(mp)
# una fila por día: si hay duplicados con etiqueta distinta, ese componente se excluye ese día
def agg(g, k):
    v = g[k].dropna().unique(); return v[0] if len(v) == 1 else np.nan
days = sorted(d.dia.unique()); lab = pd.DataFrame({'dia': days})
for k in ('d1', 'h4', 'am', 'pm'): lab[k] = [agg(d[d.dia == x], k) for x in days]
def T_of(dia):
    t = pd.Timestamp(dia, tz='UTC') + pd.Timedelta(days=1, minutes=30)
    return t if t.weekday() != 5 else t - pd.Timedelta(days=1)       # SPEC §2: D+1 sábado -> T = D
lab['T'] = [T_of(x) for x in lab.dia]
lab = lab[(lab['T'].dt.weekday != 6) & (lab['T'] <= m5.index.max()) & (lab['T'] >= m5.index.min() + pd.Timedelta(days=15))]
v = compute_votes(m5, h1, list(lab['T'])).reset_index(drop=True)
lab = pd.concat([lab.reset_index(drop=True), v], axis=1)
rows = []
for comp, cands in (('d1', ('d1_A', 'd1_B')), ('h4', ('h4_A', 'h4_B')), ('am', ('am_A', 'am_B')), ('pm', ('pm_A', 'pm_B'))):
    s = lab.dropna(subset=[comp]); n = len(s)
    if n == 0: continue
    base = s[comp].value_counts(normalize=True).max()
    for c in cands:
        a = s[c]; l = s[comp]; both = (a != 0) & (l != 0)
        rows.append(dict(componente=comp, candidato=c, n=n, etiq_no_neutral=round((l != 0).mean(), 2), cobertura_alg=round((a != 0).mean(), 2),
                         exactitud_3clases=round((a == l).mean(), 3), baseline_mayoria=round(base, 3),
                         n_ambos_dir=int(both.sum()), acuerdo_dir=round((a[both] == l[both]).mean(), 3) if both.any() else np.nan,
                         contrario=round((a[both] != l[both]).mean(), 3) if both.any() else np.nan))
res = pd.DataFrame(rows); print(res.to_string(index=False))
res.to_csv(f'analysis_v13/acuerdo_{year}.csv', index=False); lab.to_csv(f'analysis_v13/votos_vs_etiquetas_{year}.csv', index=False)
