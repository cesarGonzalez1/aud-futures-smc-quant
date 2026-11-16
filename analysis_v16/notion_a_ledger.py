"""Convierte el export de Notion al ledger que pide reproducir_ledger.py.
Uso: python analysis_v16/notion_a_ledger.py <notion.csv> <salida.csv>
- Solo filas con opero == Yes y con Entry price / SL / TP numericos.
- fecha = 'Dia del testing' si es backtest, si no 'Date'. es_backtest = fechas distintas; iguales o vacío = trade real. Se imprime cuantas filas son de cada tipo."""
import sys, pandas as pd
src, out = sys.argv[1], sys.argv[2]
N = pd.read_csv(src)
N.columns = [c.strip() for c in N.columns]
print("filas totales:", len(N), "| opero=Yes:", int((N["opero"].astype(str).str.strip().str.lower() == "yes").sum()))
N = N[N["opero"].astype(str).str.strip().str.lower() == "yes"].copy()
N["fecha_testing"] = pd.to_datetime(N["Dia del testing"], errors="coerce")
N["fecha_date"] = pd.to_datetime(N["Date"], errors="coerce")
# Regla del usuario: Date == Dia del testing -> trade REAL; fechas distintas -> backtest; Dia del testing vacío -> real.
N["es_backtest"] = N["fecha_testing"].notna() & (N["fecha_testing"].dt.normalize() != N["fecha_date"].dt.normalize())
N["fecha"] = N["fecha_testing"].fillna(N["fecha_date"])
N["lado"] = N["Dirección"].astype(str).str.strip().str.capitalize()
for a, b in (("entry", "Entry price"), ("sl", "SL"), ("tp", "TP")):
    N[a] = pd.to_numeric(N[b], errors="coerce")
N = N[N["lado"].isin(["Long", "Short"]) & N[["entry", "sl", "tp"]].notna().all(axis=1)]
print("con lado y precios completos:", len(N))
print("por año de 'fecha' y tipo:"); print(N.groupby([N.fecha.dt.year, "es_backtest"]).size())
N[["fecha", "lado", "entry", "sl", "tp", "es_backtest"]].sort_values("fecha").to_csv(out, index=False)
print("escrito:", out)
