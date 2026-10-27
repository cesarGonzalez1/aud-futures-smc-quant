# Regla fijada ANTES de ver resultados V9 vs journal (2026-10-23)
- Fecha ledger D = fecha CDMX. Sesión UTC = día D+1 (validado: precio de entrada cae en rango proxy 35/38 con +1 vs 13/37 con +0; sin mirar V9).
- Universo: solo trades con datos proxy (hasta 2025-07-01) => solo 2024 (41 filas). 2026 (70) SIN datos: NO evaluado.
- "Mismo trade": V9 tiene entrada en día UTC D+1 con mismo lado que el journal.
- "Lado contrario": V9 entró ese día solo en lado opuesto. "V9 no operó": ninguna entrada ese día.
- R comparado: journal R (bruto, hindsight) vs V9 r_net (neto de costos). No comparables 1:1; se reporta aparte.
- Fechas repetidas del journal se marcan; n<30 por celda = inconcluso. Una sola corrida: V9 baseline (mss). Registro test múltiples: +1.
