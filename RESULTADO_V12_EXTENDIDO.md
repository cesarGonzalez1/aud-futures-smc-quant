# V12 con datos hasta 2026-10 + comparación con journal 2026 (2026-10-26)
Corrida 3 de V12 (sin cambiar parámetros). Ingesta del usuario: AUDUSD M5 472,519 velas. 6A M5 real = 0 filas (Yahoo no sirve histórico).

## 1. V12 extendida (118 ops, 2020-08→2026-10)
- Win 35.6%, neto -0.316R (IC95 [-0.54,-0.08]), bruto -0.065R, costo 0.25R/op. Primera 95 ops idénticas a la corrida previa.
- Primaria A > B+C: NO se confirma (A -0.48R n=43; B+C -0.20R n=66; IC dif [-0.77,+0.20]).
- Periodo nuevo fuera de muestra 2025-07→2026-10: n=23, -0.34R (IC [-0.81,+0.21]) → inconcluso. 2026: n=13, -0.02R.
- Subconjunto ≥2022-11 (post-hoc, solo descriptivo): A -0.67R (n=25) vs B+C -0.02R (n=43), IC dif [-1.23,-0.05]. A es PEOR, opuesto a la hipótesis. No accionable sin nueva hipótesis registrada.
- Perfecto (A∧vela∧eq_vwap): n=7, -0.88R. eq_vwap -0.59R (n=35, IC<0).

## 2. V12 vs journal 2026 (regla fijada: fecha CDMX D → sesión UTC D+1, mismo lado)
- V12 hizo 13 trades en 2026; tu journal tiene 70 filas (65 fechas). 6 filas coinciden en día y lado, entradas a 0.2-8.7 pips (mismo trade).
- Resultado coincide en 3 de 5 trades únicos (158, 169, 242 sí; 149 journal +1.8R vs V12 stop; 75/193 mismo trade 25-may: journal loss vs V12 target por TP distinto).
- V12 NO operó en 63 de tus 70. 7 de 13 V12 caen en días sin fila del journal (el journal no cubre todos los días).

## 3. Por qué V12 se salta tus trades (2024, 38 días con mercado, puerta por puerta)
- 36/38 mueren en puerta 1 (bias ≥3/4 a favor de tu lado). 1 sin IFVG, 1 pasa.
- Bias automático: voto neutral (0) 46% D1, 47% H4, 56% NY AM, 63% NY PM; "3 de 4" solo 9% de los días.
- Donde marcaste D1 (n=31, 2024), el algoritmo es neutral 45-58%; entre no neutrales coincide 29-31% (n=13-17).
- Tus etiquetas bias_d/4h/ny_am van a favor de tu lado 87%/92%/70% (backtest manual) y 95%/90%/86% (en vivo/sim/Apex, n=21-22). Puede haber sesgo post-hoc.
- Conclusión: el resultado negativo de V12 mide "tus entradas + un bias automático que no reproduce el tuyo". NO es veredicto sobre tu método.

## Siguiente (requiere al usuario)
Describir la regla exacta para marcar Alcista/Bajista/Acumulativa en D1, 4H, NY AM y NY PM. Codificarla y calibrarla por ACUERDO con las etiquetas del journal (no por P&L), preregistrar V13.
Tests múltiples V12 acumulados: 3 corridas + subconjuntos descriptivos.
