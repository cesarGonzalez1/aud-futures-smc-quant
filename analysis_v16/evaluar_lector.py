"""Califica al agente `lector-capturas` contra respuestas conocidas (PRE-REGISTRADO en SPEC_LECTOR_CAPTURAS.md).
Uso: python analysis_v16/evaluar_lector.py <verdad.csv> <salida_agente.csv>
verdad.csv  : name,direccion,entry,sl,tp  (valor vacío = la captura NO trae ese dato -> el agente debe poner '?')
salida.csv  : name,direccion,entry,sl,tp  (el agente pone '?' cuando no puede leer)"""
import sys, pandas as pd, numpy as np
V = pd.read_csv(sys.argv[1], dtype=str).set_index("name"); A = pd.read_csv(sys.argv[2], dtype=str).set_index("name")
J = V.join(A, rsuffix="_ag", how="left")
def num(x):
    try: return float(x)
    except (TypeError, ValueError): return np.nan
inventados = 0; res = {}
for c in ("direccion", "entry", "sl", "tp"):
    ok = tot = 0
    for _, r in J.iterrows():
        v, a = r[c], r[c + "_ag"]
        v_vacio = pd.isna(v) or str(v).strip() == ""
        a_vacio = pd.isna(a) or str(a).strip() in ("", "?")
        if v_vacio:
            if not a_vacio: inventados += 1          # el agente dio un dato que la captura no trae
            continue
        tot += 1
        if c == "direccion": ok += (not a_vacio) and str(a).strip().lower() == str(v).strip().lower()
        else: ok += (not a_vacio) and abs(num(a) - num(v)) < 1e-9
    res[c] = (ok, tot)
for c, (ok, tot) in res.items(): print(f"{c:9s} exactos {ok}/{tot} = {ok/tot:.0%}" if tot else f"{c:9s} sin casos")
print("datos INVENTADOS (dio valor donde la captura no trae):", inventados)
d = res["direccion"]; p = [res[c] for c in ("entry", "sl", "tp")]
pr = sum(o for o, _ in p) / max(1, sum(t for _, t in p))
aprob = inventados == 0 and d[1] and d[0] / d[1] >= 0.9 and pr >= 0.8
print(f"precios exactos (entry+sl+tp): {pr:.0%} | APROBADO: {'SI' if aprob else 'NO'}  (reglas: 0 inventados, direccion>=90%, precios>=80%)")
