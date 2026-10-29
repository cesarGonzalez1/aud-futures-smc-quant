# PROGRESS — Fase 4: V1/V2/V3/V4 backtesteadas

**V4 corrido sobre 5 años. 74/74 tests verdes. Nada roto.**

## Comparativa de hipótesis (EXPLORATORIO — proxy AUD/USD 5 años, costos reales)
| | TF señal | Stop | Ops | Win% | R bruto | R neto | Gate ADR-009 |
|---|---|---|---|---|---|---|---|
| V1 (ADR-007) | H1 | mecha M5 | 40 | 35% | — | −0.27R | insuficiente |
| V2 (ADR-008 AMD) | H1 | mecha M5 | 49 | 39% | — | −0.31R | insuficiente |
| V3 (ADR-009) | M5 | mecha M5 | 245 | 39% | +0.12R | −0.76R | preliminar |
| **V4 (ADR-010)** | M5 | **swing H1** | 185 | **49%** | −0.05R | **−0.35R** | preliminar |

## Hallazgo V4 (honesto)
La hipótesis de costo de ADR-010 **se confirmó pero no bastó**:
- Stop H1 amplió riesgo medio 4.5→19.4 pips (4.3×) → `cost_r` 0.87R→0.29R (≈3× menos
  costo, justo lo predicho por el diagnóstico de V3). ✅ mecánica correcta.
- PERO edge bruto se dio vuelta +0.12R→−0.05R: stop más amplio + target aún en swing
  M5 (cercano) → reward:risk peor (avg_win 0.78R→0.39R), aunque win rate sube a 49%.
- Neto −0.35R: mejor que V3, aún negativo, peor que V1. **Trade-off, no arreglo.**

## Ninguna hipótesis es rentable neta todavía
V1-V4 exploratorias, todas negativas netas. Aprendizaje acumulado (valioso):
- La señal genera edge bruto en M5 (V3: +0.12R).
- Costo y reward:risk están en tensión: bajar costo (stop ancho) mata el R geométrico
  mientras el target siga en el swing M5 cercano.
- **Próximo paso lógico (no iniciado):** mover también el target (ej. swing H1 opuesto,
  simétrico al stop) para restaurar el reward:risk — pero eso YA es optimización sobre
  resultados vistos → activaría control de tests múltiples + Deflated Sharpe (6.2).

## Estado global
Fases 1-3 cerradas. Fase 4: 4 hipótesis, 7 experimentos preservados (ninguno
sobrescrito). CLAUDE.md v3.2. 74/74 tests. Makefile: backtest / -v2 / -v3 / -v4.

## Siguiente (opciones, requieren decisión del usuario)
- V5: target también estructural H1 (simétrico al stop V4) — ⚠️ activa 6.2/Deflated Sharpe.
- Filtro de spread / instrumento de menor costo (ataca costo sin tocar R geométrico).
- Análisis formal por POI (order blocks dominan en M5).
- Fase 5 (reportes/cohortes) si se pausa la exploración de estrategia.

---

# ADR-014/ADR-015 — V6 y V7 corridos en el entorno real del usuario (2026-07-05)

**V6 (señal V1 + stop swing H1, ADR-014):** 29 operaciones, gate NO cruzado
(<100, ADR-009). Sin trailing ALL=-0.302R; con trailing (ADR-013) ALL=-0.213R
(mejora ~0.09R, mismo patron que V5+Trailing: el trailing ayuda cuando el stop
de partida es ancho). Muestra demasiado pequena para leer como confirmacion.

**V7 - jerarquia discrecional completa (ADR-015), PIVOTE:** por pedido del
usuario, se codifico por primera vez la jerarquia completa (EQL/EQH+sweep ->
MSS/CISD -> contexto Quarter Theory -> FVG/IFVG -> target BOS/Quarter Theory),
no solo las hipotesis parciales V1-V6. Modulos nuevos: `features/mss_cisd.py`,
`features/quarter_theory.py`, `features/liquidity_target.resolve_target_v7`,
`strategy/liquidity_sweep_ifvg_v7.py`, `backtest/run_v7.py`. 114/114 tests en
verde (12 nuevos). Resultado real (5 anos):

| version | ops | win%  | expectancy neta |
|---|---|---|---|
| V1 | 40  | 35%   | -0.27R |
| V2 | 49  | 39%   | -0.31R |
| V3 | 245 | 39%   | -0.76R |
| V4 | 185 | 49%   | -0.35R |
| V5 | 191 | 50.3% | -0.31R |
| V6 | 29 (gate no cruzado) | 37.9% | -0.30R |
| V7 (ADR-015) | 197 | 52.8% | -0.18R (mejor de todas) |

**V7 es la primera version desde V3 en cruzar el gate de 100 operaciones, con
el win rate mas alto y la expectativa neta menos negativa de las 7 versiones.**
Sigue sin ser rentable: `avg_win` (0.67R) < `avg_loss` (1.13R) - el target de
Quarter Theory (un cuarto = 0.0025) es cercano frente a un stop de swing H1
ancho, reward:risk sigue en contra pese a que la confirmacion MSS/CISD sube el
win rate. Confirmacion: CISD domina (170/197) sobre MSS (27/197). SMT no
implementado (falta ingesta de 6N, pendiente de decision del usuario).

**Motor de senales (asistente):** NO se construye todavia - regla explicita
del ADR-015: se activa solo sobre una regla validada (gate + neta positiva).
Proximo paso logico antes de eso: probar `quarter_target(..., n_levels=2)`
(saltar un cuarto) para intentar equilibrar el reward:risk sin tocar el stop,
como V7b - requiere decision del usuario porque ajustar tras ver el resultado
de V7 activa el control de tests multiples (seccion 6.2).

---

## V7b (ADR-015, ajuste post-V7, 6.2 activado) — RECHAZADO, V7 sigue siendo la mejor version

Se probo `quarter_n_levels=2` (target salta un cuarto en vez del inmediato)
para intentar subir `avg_win` sin tocar el stop. Resultado real (5 anos): 184
ops (cruza gate), win rate cae a 39.1% (vs 52.8% de V7), `avg_win` sube a 1.27R
(vs 0.67R) pero no compensa la caida de aciertos -> expectancy **-0.235R, PEOR
que V7 (-0.18R)**. Conclusion honesta: alejar el target reduce la tasa de
acierto mas de lo que gana en tamano de ganancia neta. **Se descarta V7b. V7
(quarter_n_levels=1, el cuarto inmediato) sigue siendo la mejor estrategia real
validada para 6A** — regla fija: siempre priorizar la version con mejor
desempeno real en backtest al proponer el siguiente paso.

Con V7 y V7b ya comparados (2 variantes tras ver datos), si se prueba una
tercera variante de este mismo eje (target), corresponde activar Deflated
Sharpe/control formal de tests multiples (seccion 6.2) antes de confiar en
cualquier mejora marginal.

---

## V8 (ADR-015, hipotesis 1 sobre el STOP, predefinida) — RECHAZADO, V7 sigue siendo la mejor version

Hipotesis: igual que V7, pero el stop usa el swing M5 (`last_swing_high`/
`last_swing_low`, ya calculado por `features/structure.py` sobre M5 pero nunca
usado como stop en V1-V7) en vez del swing H1 mapeado (ADR-010). Ataca el otro
lado de la razon R (riesgo, no recompensa), a diferencia de V7b.

**Primer resultado (sin filtro de realismo):** 221 ops, expectancy -0.139R
(aparenta ser MEJOR que V7 -0.18R) pero con red flags evidentes: win rate se
desploma a 33.5% (vs 52.8% V7), max drawdown se dispara a 84.7R (vs 39.5R V7),
y el resultado esta dominado por un solo trade de +76.7R neto (2021-11-16,
riesgo de entrada de solo 0.00002 = 0.2 pips). **Diagnostico: artefacto.** Un
swing M5 puede quedar a una distancia minima e inoperable del precio de
entrada (spread/slippage por si solos lo consumen; el tamano de posicion
implicito para arriesgar un monto fijo seria impracticable) - eso infla el
R-multiple de forma irreal, no es edge real.

**Con filtro de realismo de ejecucion** (`min_stop_atr_frac=0.3`, riesgo minimo
= 0.3 x ATR de la barra del sweep - filtro de ejecutabilidad, no ajuste
post-resultado): el trade de +76.7R desaparece, y el resultado real es **211
ops, win rate 35.1%, expectancy -0.301R - PEOR que V7 (-0.18R)**, similar a
V4/V5/V6. **Se descarta V8. V7 (stop en swing H1) sigue siendo la mejor
estrategia real validada para 6A** - la version base (swing H1, mas ancho)
resulta superior a la version con stop M5 mas ajustado, una vez corregido el
artefacto de stops irrealmente pequenos.

**Regla que queda para el proyecto:** cualquier hipotesis futura que use un
swing M5 (u otro nivel de bajo timeframe) como stop DEBE incluir un filtro de
distancia minima realista (ATR o equivalente) desde el primer intento, no como
ajuste posterior - la ausencia de ese filtro no es una variante valida a
comparar, es un error de diseno del backtest.

Con V7, V7b y V8 ya probados y comparados, la proxima hipotesis distinta
(separar MSS vs CISD, o SMT vs 6N) puede considerarse la tercera variante
independiente del eje de confirmacion/entrada - si se sigue iterando sobre
stop/target especificamente, ya van 3 variantes de ese eje (V7, V7b, V8) y
corresponde activar el control formal de tests multiples (6.2) antes de
confiar en cualquier mejora marginal futura sobre ese mismo eje.

---

## MSS vs CISD por separado (ADR-015) — NUEVA MEJOR ESTRATEGIA REAL: V9 (MSS-only)

**Primero, desglose retrospectivo de V7** (mismas 197 operaciones, agrupadas
por que confirmo primero): CISD domina la muestra (170/197) con win rate 51.8%
y expectancy -0.241R; MSS solo aparece en 27/197 pero con win rate 59.3% y
expectancy +0.207R - senal interesante pero MUESTRA INSUFICIENTE (<100, no se
puede concluir nada, ADR-009).

**Por que la muestra de MSS parecia tan chica:** en V7, cuando ambas
confirmaciones (MSS y CISD) ocurren en la misma ventana, se usa la que llega
PRIMERO - y CISD casi siempre gana la carrera (aparece mas rapido tras el
sweep). Eso no significa que MSS ocurra poco; significa que MSS casi siempre
llega despues de que CISD ya confirmo. Para medir esto bien, se corrio una
variante que exige SOLO MSS (CISD ni compite por el timestamp) y otra que
exige SOLO CISD, con generacion independiente (no un filtro post-hoc):

| variante | ops | win% | expectancy | max_drawdown_r |
|---|---|---|---|---|
| V7 (any, mezclado) | 197 | 52.8% | -0.18R | 39.5 |
| CISD-only | 195 | 52.8% | -0.177R | 38.59 |
| **MSS-only (V9)** | **117** | **53.8%** | **-0.119R (mejor de todas las versiones)** | **21.24 (la mas baja)** |

**MSS-only cruza el gate de 100 operaciones (117) y es AHORA la mejor
estrategia real validada para 6A**: mejor expectancy que V7 (-0.119R vs
-0.18R) Y el max drawdown mas bajo de todas las versiones (21.24R vs 39.5R de
V7). CISD por si sola es practicamente identica a V7 combinado (tiene sentido:
CISD gana la carrera en 170/197 casos de V7). **Se promueve a V9: V7 +
`confirmation_require='mss'` (exigir MSS como unica confirmacion, no "cualquiera").**

**Nota de rigor:** este es ya el tercer parametro probado en el eje de
confirmacion (any / cisd-only / mss-only) - la mejora de V9 sobre V7 es
consistente con la senal que ya habia aparecido en el desglose retrospectivo
(no es un hallazgo aislado de una sola corrida), pero antes de usar V9 para
cualquier decision real conviene, en cuanto se agregue mas historia o se
pruebe otra variante mas sobre este eje, activar el control formal de tests
multiples (Deflated Sharpe, seccion 6.2).

**Sigue siendo neta negativa (-0.119R).** Sigue sin ser una estrategia lista
para el motor de senales - pero es el mejor punto de partida real que hay para
seguir iterando (p.ej. combinar la idea de V9 con Quarter Theory a 2 niveles
ahora que el win rate base es mas alto, o revisar si el stop sigue siendo el
cuello de botella con esta confirmacion mas selectiva).

---

## ADR-017 parte 2 — Motor de señales en VIVO: funcionando de punta a punta

`decision_engine/live_signal.py` (evalúa si hay una señal V9 vigente al
momento actual) + `decision_engine/run_signal.py` (CLI: `make signal`).
Recalibra el `ConfluenceScorer` con TODO el histórico disponible en cada
corrida (no requiere guardar pesos en disco) y evalúa la barra más reciente.
Probado end-to-end con datos reales del proyecto: 117 operaciones históricas,
señal correctamente marcada como "no vigente" cuando la última señal V9 real
quedó fuera de la ventana de 6 horas. 140/140 tests en verde (4 nuevos).

Limitación honesta documentada en el módulo: si no hay señal, no explica
todavía POR QUÉ capa por capa (no hubo sweep vs no confirmó MSS vs no hubo
IFVG) - eso queda pendiente como mejora futura.

Requiere que el usuario corra `make ingest` antes de cada evaluación para que
M5/H1 tengan la barra de hoy - el motor no descarga nada, solo evalúa.

---

## V9 + variantes de target/stop ya descartadas — NINGUNA mejora el baseline

Se probo si las dos hipotesis ya rechazadas sobre V7 "cualquiera" (V7b: target
Quarter a 2 niveles; V8: stop en swing M5) se comportan distinto combinadas con
la confirmacion mas selectiva de V9 (MSS-only). Resultado real (5 anos):

| variante | ops | win% | expectancy | max_drawdown_r |
|---|---|---|---|---|
| **V9 (baseline)** | 117 | 53.8% | **-0.119R (mejor)** | 21.24 |
| V9b (+ quarter_n_levels=2) | 114 | 41.2% | -0.124R | 31.83 |
| V9-stopM5 (+ stop swing M5) | 120 | 43.3% | -0.128R | 20.39 |

**Ninguna combinacion mejora el baseline de V9.** Ambas repiten el mismo
patron ya visto en V7b y V8: subir avg_win (1.38R y 1.23R respectivamente)
cuesta demasiado win rate (cae a 41-43% vs 53.8%) y el neto empeora. **V9
(MSS-only, target Quarter Theory inmediato, stop swing H1) sigue siendo,
confirmado por triplicado, la mejor estrategia real validada para 6A.**

Con 5 variantes ya comparadas sobre estos ejes (V7, V7b, V8, V9b, V9-stopM5) y
3 sobre el eje de confirmacion (any/cisd/mss), cualquier intento adicional de
ajustar target o stop sobre esta misma jerarquia deberia pasar primero por el
control formal de tests multiples (Deflated Sharpe, seccion 6.2) antes de
confiar en el resultado. Los ejes que quedan sin explorar y no caen en este
riesgo (por ser variables nuevas, no ajustes del mismo parametro): SMT (6N,
requiere ADR-016) y una revision de la ventana de busqueda de MSS/CISD
(`confirmation_lookback`/`entry_lookback`), que todavia usa los valores por
defecto heredados de V7 sin haber sido probada explicitamente.

---

## ADR-016 — Ingesta 6N + SMT: implementado y probado, PENDIENTE datos reales

Se implemento `features/smt.py` (divergencia SMT 6A vs 6N, D1, point-in-time),
se registro 6N en `config/settings.yaml` (cross_asset, yahoo_futures, mismo
patron que 6A) y se extendio `data/sources/yahoo_futures.py` con el ticker
`6N=F`. 3 tests nuevos con datos sinteticos, 119/119 en verde.

**No se pudo ingerir 6N de verdad en este entorno** (sin acceso de red a
`query1/query2.finance.yahoo.com`, confirmado con un intento real que fallo
con 403). Falta correr `make ingest` (o `python -m data.ingest`) en el entorno
del usuario para traer 6N y poder correr cualquier backtest que use SMT con
datos reales. Hasta entonces, ninguna version de estrategia (V7-V9) incluye
SMT - siguen operando con las 2 de 3 confirmaciones ya disponibles (MSS/CISD).

**Limitacion de granularidad (heredada de ADR-006):** Yahoo solo da 6A/6N en
D1 - SMT solo puede evaluarse a nivel D1 (como el bias HTF), no M5 como
MSS/CISD. Es una restriccion de la fuente, documentada, no una aproximacion.

---

## V10 (ADR-016, gate diario SMT sobre V9) — DESCARTADO, muestra colapsa a 3 operaciones

El usuario corrio `make ingest` + `python -m backtest.run_v10` en su entorno
real (6A/6N ya ingeridos). Resultado real (5 anos): **de las 117 operaciones
de V9, solo 3 coinciden con un dia donde hay divergencia SMT (6A vs 6N)
alineada con el lado del trade.** Esas 3 operaciones: 0% win rate, expectancy
-1.06R. Gate no cruzado (<100, ADR-009) - muestra insuficiente para concluir
nada sobre si SMT "funciona", solo que el gate tal como esta disenado es
demasiado restrictivo para combinarse con una estrategia ya selectiva
(MSS-only).

**Se descarta el gate diario de V10. V9 (MSS-only, sin SMT) sigue siendo la
mejor estrategia real validada para 6A.** SMT como gate obligatorio diario
sobre una entrada ya M5-selectiva es demasiado raro como para aportar muestra
util - habria que revisar el diseno de la integracion (p.ej. SMT como contexto
informativo en vez de gate obligatorio, como se hizo con Quarter Theory en la
capa 3) antes de volver a intentarlo, no simplemente reintentar con mas datos.

Con V7, V7b, V8, V9b, V9-stopM5 y V10 ya probados y descartados frente a V9,
la version de referencia para cualquier decision futura sobre 6A sigue siendo
**V9: jerarquia completa (ADR-015) + confirmacion exigida SOLO MSS + target
Quarter Theory inmediato + stop swing H1. 117 operaciones, win rate 53.8%,
expectancy -0.119R, max drawdown 21.24R.**

---

## V12 — "trade de cajón" del usuario (SPEC_V12.md) — NEGATIVO, sin setup que funcione
Hipótesis nueva predefinida (no ajuste de V9): bias ≥3/4 + desde 6:30 pm + sweep clasificado por VWAP (ancla 17:00 CT, ±1σ) + IFVG M5 + SL en extremo del sweep + TP RR 1.6-1.8 por zonas, máx 1/día. Setups por hora de entrada: A0/A/B/C. Módulos: `features/vwap.py`, `features/daily_candle.py`, `strategy/liquidity_sweep_ifvg_v12.py`, `backtest/run_v12.py`. 182/182 tests. Experimento `2026-10-24_strat_v12_trade_cajon` (1 corrida registrada).
**Resultado (proxy 2020-07→2025-07):** 95 ops (<100, insuficiente), win 35.8%, neto −0.318R (IC95 [−0.57,−0.06]), bruto −0.061R, costo 0.26R/op. Hipótesis primaria A>B+C NO se confirma (A −0.43R n=34; B+C −0.26R n=54; IC dif [−0.72,+0.36]). "Perfecto" (A∧vela∧eq_vwap) n=5 → inconcluso. Ninguna celda con n≥30 y IC>0.

### V12 sensibilidad horaria (2026-10-26): solo entradas ≥ 2022-11-01 (horario CDMX exacto)
50 ops, win 38.0%, neto −0.279R (IC95 [−0.63,+0.10]), bruto −0.002R. Primaria A>B+C NO se confirma (A −0.67R n=16 vs B+C −0.06R n=31; IC dif [−1.29,+0.15]). Mejor celda puntual B (+0.09R, n=22) = inconcluso, no hallazgo. "Perfecto" n=1. Conclusión igual que corrida completa. +1 tests múltiples (total V12: 2 corridas).

### V12 extendida a 2026-10 + journal 2026 (2026-10-26) — ver RESULTADO_V12_EXTENDIDO.md
118 ops, -0.316R neto; periodo nuevo n=23 inconcluso (-0.34R). Journal 2026: 6 de 70 filas coinciden con V12 (13 trades). Causa principal: puerta de bias (algoritmo neutral 46-63% de los días, coincide ~30% con tus etiquetas D1). V12 no refuta tu método; refuta el bias estructural automático. Siguiente: codificar tu regla de bias y calibrar contra etiquetas (V13 preregistrada).

## 2026-10-26 — Incidente: `features/bias_user.py` sobrescrito y reconstruido (V13)
- Por error sobrescribí `features/bias_user.py` (contenía `compute_votes`) sin leerlo antes. No había respaldo.
- Reconstruido desde SPEC_V13 y validado contra las salidas guardadas de la corrida V13 original:
  - `votos_vs_etiquetas_2024.csv`: 8 columnas × 84 días → 0 diferencias.
  - `confluence.csv` (1304 días): h4, ny_am, ny_pm 100% idénticos; d1 3 difs (2020-07-03, 2025-01-01, 2025-07-01); dir_ayer/dir_hoy 4 difs cada uno (bordes de datos/feriados). Ninguna de esas fechas tiene operación en trades.csv (235 ops).
- V13 NO se re-corrió (corrida registrada única, tests múltiples: V13 = 1). Mi calibración independiente (scripts/calibrate_bias.py, SPEC_BIAS_USER.md) se descartó por redundante con SPEC_V13/analysis_v13.
- Siguiente paso: hold-out 2026 → `python analysis_v13/calibrar_bias.py "<notion_all.csv>" 2026` en la máquina del usuario.

## 2026-10-28 — Hold-out 2026 de bias + V14 (pre-registrada, aún NO corrida)
- Hold-out etiquetas 2026 (n≈132-139 días): am_B 77.7%, h4_B 64.9%, d1_B 53.8% aceptados; pm_A 47.8% rechazado (<50%, SPEC_V13 §4). pm_B 52.2% no se elige (sería seleccionar con el hold-out).
- Decisión del usuario: NY PM = información, no puerta. SPEC_V14.md: puerta = d1+h4+ny_am alineados (3 de 3); `pm_rel` por operación. Prueba limpia = entradas ≥ 2026-01-01; antes de eso solo descriptivo.
- Puerta abierta en 19.4% de días (V13: 30.6%) sobre datos ≤2025-07 → esperado ~20-30 ops en 2026: probable n<30 (inconcluso, ADR-009). Se acepta; no se relaja la puerta para ganar muestra.
- Tests múltiples acumulados: V13 = 1 corrida, V14 = 1 (pendiente de correr: `make backtest-v14`).
- 4H explicado por el usuario (lateral = muchas velas sin HH/LL, ~3-5 días): candidato `h4_C` N=4 días, para versión posterior.

## 2026-10-28 — V14 re-evaluada con costos reales de 6A (SPEC_COSTOS_6A.md)
- Mismas 192 ops de V14; costo viejo 0.244R → real 0.057R (0 ticks) / 0.103R (1 tick) / 0.150R (2 ticks) por op.
- Con 1 tick: limpia 2026 (n=22) −0.176R IC [−0.69,+0.34]; dev (n=170) +0.055R IC [−0.15,+0.26]; todo +0.028R. Con 2 ticks ≈ 0. Nada significativo.
- Buckets (1 tick, todo): A +0.204R (n=93, IC [−0.08,+0.49]), A0 +0.037, B −0.069, C −0.266. Con riesgo ≤ $500: A +0.244R (n=56), C −0.458R IC [−0.90,−0.02].
- 31% de las ops del motor (60/192) arriesgan > $500 con 6 contratos (stop del motor > 8.3 pips): el motor no replica los stops del usuario en ese tercio.
- Solape con ledger: 2026 → 6 de 22 señales V14 caen en día de trade del usuario (5 mismo lado); 6 de sus 70 trades 2026 están en día de señal V14. 2024: 5/34 (4 mismo lado). El motor NO reproduce lo que el usuario opera.
- Ledger 2026 por fuente: backtest_manual n=45 +0.75R; PA_apex n=13 +0.52R; real_cuenta n=7 −0.39R; tiempo_real_sim n=5 +1.01R (n muy chicos; backtest manual sujeto a sesgo de hindsight).

## 2026-10-28 — V15 pre-registrada (aún NO corrida): puerta ">=2 a favor y ninguno en contra"
- Motivo: V14 (3 de 3) ~20 ops/año vs ~70/año reales del usuario. Ledger 2026 (n=68): 3 a favor +1.00R (28), 2+neutral +0.93R (15), 2 a favor + 1 en contra +0.16R (19). Patrón visto post-hoc; se prueba sobre el motor 2020-2026. SPEC_V15.md.
- Entrada SIEMPRE = IFVG posterior al sweep (≤12 velas M5, abre la vela siguiente). Primaria: todas las entradas con costo real 6A a 1 tick, A > B+C.
- Con confluence.csv de V14: la puerta abriría 711 de 1649 días (43%) → ~68 ops/año esperadas.
- Tests múltiples: V13 = 1, V14 = 1, V15 = 1 (pendiente: `make backtest-v15`, una sola vez).

## 2026-10-29 — V15 CORRIDA (única): puerta >=2 a favor y ninguno en contra
- 390 ops (~60/año), puerta abierta 43.1% de 1649 días. Evidencia preliminar, no concluyente (ADR-009).
- PRIMARIA (costo real 6A, 1 tick): neto +0.003R IC95 [-0.13,+0.14]; bruto +0.103R; costo 0.100R; win 42.1%. A +0.072R (n=180) vs B+C -0.052R (n=190); dif +0.124R IC [-0.15,+0.40] → NO se confirma A > B+C.
- Slippage: 0 ticks +0.048R [-0.07,+0.18]; 2 ticks -0.043R [-0.18,+0.10]. Costo modelo viejo: -0.132R IC<0 (referencia, irreal para 6A).
- 2026 (n=55): -0.058R [-0.40,+0.29]; <2026 (n=335): +0.013R. Por año: 2021 +0.14, 2022 -0.09, 2023 -0.07, 2024 -0.14, 2025 +0.21.
- Buckets: A +0.072, A0 -0.105 (n=20), B +0.081, C -0.224 [-0.49,+0.05]. B no es peor que A.
- gate_tipo: tres +0.035R (191) vs dos_neutral -0.028R (199): sin diferencia.
- pm_rel (informativo): a_favor +0.316R (82) IC [+0.02,+0.61]; en_contra +0.048R (94); neutral -0.138R (214). Único IC>0 entre ~15 celdas descriptivas: NO se lee como hallazgo (comparaciones múltiples); pm_A no pasó hold-out como proxy de las etiquetas del usuario (47.8%).
- trigger: eq_extremo +0.126R, eq_vwap -0.012R, sweep_extremo -0.197R (todos IC cruzan 0).
- Riesgo <= $500 con 6 contratos: 251 de 390 ops; -0.046R [-0.21,+0.12]; A +0.118R (102).
- Lectura: el motor codificado está en breakeven con costos reales; no se distingue de 0 (con n=390 el IC descarta edges > ~+0.14R/op). Brecha con el ledger (backtest manual +0.75R, cuenta real/sim n=25 menos) sin explicar: sesgo de hindsight del backtest manual y/o información que el motor no modela (sweep "real" tras sweep "leve" — simplificación declarada en SPEC_V12 §2; stops del motor > $500 en 36% de ops).
- Tests múltiples: V13 = 1, V14 = 1, V15 = 1. No repetir V15.

## 2026-10-29 — V16 preparada (SPEC_V16.md): calibración 2024 hecha, hold-out 2026 pendiente
- Reglas nuevas del usuario (3 capturas): confirmación = IFVG o 3 velas M5 seguidas (lo primero), sin exigir EQ, SL +1 tick, TP RR 1.7 fijo.
- Reproducción del ledger 2024 (n=41, lado forzado): encuentra entrada el mismo día 44% (V15) → 63% (variante elegida); "completo" ≈12% en todas (proxy ≠ 6A). Lookback 222 = 50.
- Resultados en vivo del usuario 2026 (cuenta/PA/sim, n=22): R medio +0.34 (IC95 [-0.34,+1.10]); sin un +6R: +0.07R; mediana -1R; win 45%. Backtest manual 2026 (n=43): +0.75R, win 60% → probable hindsight. Consistente con el motor ~0R.
- Pendiente: hold-out `make reproducir-ledger ... YEAR=2026`; luego, si acepta, `make backtest-v16` (una vez).
