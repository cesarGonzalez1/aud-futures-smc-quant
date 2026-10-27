# V9 vs journal (2024) — 2026-10-23
Regla: REGLA_PREREGISTRADA.md (fijada antes). Una corrida V9 baseline (mss) → +1 en control de tests múltiples.

## Cobertura
- Proxy AUDUSD M5 termina 2025-07-01 → los 70 trades de 2026 NO evaluables (Dukascopy bloqueado en este entorno; falta ingesta en máquina del usuario o IBKR).
- Evaluables: 41 filas de 2024, todas backtest_manual (discrecional, hindsight, gradiente 'siguió plan' mezclado).
- Fecha ledger = fecha CDMX; sesión UTC = D+1 (precio entrada en rango proxy 35/38 vs 13/37). 3 viernes (02-16, 02-23, 03-08) → mercado cerrado con D+1; con D+0 02-23 y 03-08 sí caen en rango.

## Resultado (n=41; 3 sin mercado con D+1)
| Estado | n |
|---|---|
| V9 no operó ese día | 36 |
| V9 mismo lado | 2 |
| V9 lado contrario | 0 |
| mercado cerrado/sin datos | 3 |

- Mismo lado: 02-26 long (journal +0.67R win; V9 stop, −1.23R neto) y 03-27 long (journal +2.64R win; V9 target, +0.13R neto). Discrepan en 1 de 2.
- Sensibilidad D+0: 0/41 mismo lado. Conclusión no depende de la alineación.
- Contexto: V9 en 2024 hizo 22 ops (13 long, 9 short), 36% win, −6.17R neto, en días casi disjuntos del journal.

## Lectura honesta
- El journal discrecional 2024 y V9 programado casi no comparten trades: son dos estrategias distintas en la práctica, no "V9 automatiza lo que haces".
- n=2 coincidencias → no se puede decir nada de R comparado. Inconcluso.
- Journal 2024 (R bruto, hindsight) vs V9 (neto, sin hindsight) no es comparación justa; lo sería con costos y sin hindsight en el journal.
- Por qué V9 no entra: no medido. Candidatos (hipótesis, NO probadas): V9 exige MSS además de sweep+IFVG; journal entra con IFVG+sweep sin MSS en la mayoría (CISD/MSS no están como columna limpia en el ledger).
## Siguiente
1. Diagnóstico por día (sin optimizar): en las 36 fechas, ¿hubo sweep EQL/EQH? ¿hubo MSS? ¿qué capa filtró? (descriptivo, no cuenta como variante).
2. Traer datos 2025-07→hoy (make ingest en tu máquina) para evaluar los 70 de 2026, incluidos 25 real/sim/Apex.
3. V9 sin cuartos como variante registrada.
