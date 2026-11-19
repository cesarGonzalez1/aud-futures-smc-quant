"""Elige AL AZAR (semilla fija) las capturas de prueba del lector, para que no escojas las fáciles (SPEC_LECTOR_CAPTURAS.md).
Uso: python analysis_v16/muestrear_examen.py <notion.csv> [semilla=7]
Filas elegibles: opero=Yes, Entry/SL/TP numéricos, con link en 'Gráficas'. Saca 5 de desarrollo + 10 de examen."""
import sys, pandas as pd, os
N = pd.read_csv(sys.argv[1]); seed = int(sys.argv[2]) if len(sys.argv) > 2 else 7
N.columns = [c.strip() for c in N.columns]; N["fila"] = N.index
for c in ("Entry price", "SL", "TP"): N[c] = pd.to_numeric(N[c], errors="coerce")
E = N[(N["opero"].astype(str).str.lower() == "yes") & N[["Entry price", "SL", "TP"]].notna().all(axis=1) & N["Gráficas"].notna()].copy()
print("filas elegibles:", len(E))
S = E.sample(n=min(15, len(E)), random_state=seed).reset_index(drop=True)
S["name"] = [f"{str(n).strip()}#{f}" for n, f in zip(S["Name"], S["fila"])]
S["direccion"] = S["Dirección"].astype(str).str.strip().str.capitalize()
S = S.rename(columns={"Entry price": "entry", "SL": "sl", "TP": "tp"})
out = "data/raw/Notion/prueba_lector"; os.makedirs(out, exist_ok=True)
cols = ["name", "direccion", "entry", "sl", "tp"]
S.iloc[:5][cols].to_csv(f"{out}/verdad_desarrollo.csv", index=False); S.iloc[5:][cols].to_csv(f"{out}/verdad_examen.csv", index=False)
print("\nDESARROLLO (ajustar instrucciones con estas):"); print(S.iloc[:5][["name", "Gráficas"]].to_string(index=False))
print("\nEXAMEN (NO verlas hasta calificar):"); print(S.iloc[5:][["name", "Gráficas"]].to_string(index=False))
print(f"\nGuardado en {out}/. Agrega a mano 3 filas difíciles al examen (sin etiqueta / cortada / sin trade) con campos vacíos en la verdad.")
