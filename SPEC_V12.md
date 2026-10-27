# SPEC V12 — "Trade de cajón" del usuario (fijada 2026-10-23, ANTES de correr)

Origen: descripción del usuario (chat 2026-10-23). V12 = hipótesis NUEVA predefinida, no ajuste de V9.
Sin Teoría de los Cuartos (decisión previa del usuario). Una sola corrida registrada (+1 control tests múltiples).
Datos: proxy AUDUSD M5 Dukascopy 2020-07→2025-07 (único disponible). Costos: `metrics.apply_costs` (igual V7-V9).

## 1. Flujo del trade perfecto → regla
| Paso usuario | Regla V12 | Tipo |
|---|---|---|
| 6:00 pm CDMX recibe, marca NY AM, NY PM, 1D, 4H | `features.bias.build_daily_confluence` (sin cambio). Se opera solo con ≥3 de 4 alineadas (`confidence='alta'`). Se descarta la rama "2 + 2 neutrales" de V5-V9. Se registra n_alineadas (3 ó 4). | GATE |
| Vela anterior (D) mismo sentido que hoy | `prev_dir` = signo(close−open) del día de trading previo; `today_dir` = signo(close_t − open del día) en la barra del sweep. Día de trading = ancla 17:00 America/Chicago (apertura CME). `candle_aligned` = prev_dir == today_dir == dirección del trade. | ATRIBUTO (no gate) |
| Espera a 6:30 pm | No hay entradas antes de 00:30 UTC. Entrada debe ocurrir < 04:00 UTC (10 pm CDMX). | GATE |
| Marca EQL/EQH, ayudado por VWAP | VWAP de sesión anclado 17:00 CT, fuente hlc3 ponderada por volumen (volumen = ticks del proxy), bandas ±1σ ponderada (default de TradingView). Point-in-time. | ver §2 |
| Sweep real | `liquidity_sweep_high/low` existente (mecha rebasa swing y cierra de vuelta) en dirección del bias. | GATE |
| Espera IFVG en M5 | `ifvg_bear/bull` existente, dentro de 12 velas M5 tras el sweep (igual V7). Entrada = apertura de la vela siguiente a la señal. | GATE |
| SL = fin/inicio del sweep | SL = extremo del movimiento de sweep: máx high (short) / mín low (long) desde la barra del sweep hasta la barra de señal IFVG. Filtro realismo: riesgo ≥ 0.3×ATR(sweep) (igual V8). | GATE |
| TP con RR 1.6–1.8 según zonas | RR base 1.7. Zonas de liquidez en dirección del trade: PDH/PDL, extremo del día (day_hi/day_lo), borde lejano de FVG H1 sin rellenar. Si la zona más cercana está a z ≤ 1.8R → RR = clamp(z, 1.6, 1.8); si no hay zona ≤ 1.8R → 1.7. | GATE |
| 1 trade por sesión | máx 1 operación por día de sesión. | GATE |

## 2. Tipo de disparador (VWAP) — nivel L = último swing barrido
- `eq_vwap`: `equal_*_recent` y L estrictamente dentro de bandas (banda_inf < L < banda_sup) en la barra del sweep. = "EQ válido".
- `eq_extremo` ("sweep leve"): `equal_*_recent` pero L ≥ banda_sup (short) / L ≤ banda_inf (long) o fuera. Se opera igual, marcado.
- `sweep_extremo`: sin EQ reciente, L en/más allá de banda en el lado barrido. Se opera, marcado.
- Sin EQ y L dentro de bandas → NO se opera (no es setup según descripción).
- Simplificación declarada: el motor toma el PRIMER sweep calificado; el usuario espera el "sweep real" tras uno "leve". No se modela; V13 podría.

## 3. Clasificación de setup (por hora de ENTRADA, CDMX = UTC−6)
- **A0** 00:30–01:00 UTC (6:30–7 pm) — se reporta aparte, no definido por usuario.
- **A** 01:00–02:00 UTC (7–8 pm) — "seguro".
- **B** 02:00–03:00 UTC (8–9 pm) — "malo/tarde".
- **C** 03:00–04:00 UTC (9–10 pm) — "muy poco probable".
- **PERFECTO** = A ∧ candle_aligned ∧ trigger=eq_vwap ∧ n_alineadas≥3 (gate ya).
Dimensiones secundarias reportadas por separado (marginales): trigger, candle_aligned, n_alineadas (3/4), profundidad de sweep (tercil de (mecha−L)/ATR, descriptivo).

## 4. Cómo se evalúa
- Métricas por celda: n, win%, expectancy R neta, avg win/loss, IC95 bootstrap de expectancy, expectancy BRUTA (para ver costo).
- n<30 → "inconcluso" (ADR-009). Train 2020-07→2023-12 / test 2024-01→2025-07 por separado.
- Hipótesis primaria única: expectancy(A) > expectancy(B+C). Todo lo demás descriptivo (no se elige ganador por "mirar y escoger celda").
- Prohibido tras ver resultado: cambiar horas, bandas, RR, umbrales. Si se cambian → nueva versión + Deflated Sharpe (§6.2).

## 5. Límites conocidos
- Proxy AUDUSD ≠ 6A: volumen = ticks, VWAP distinto al de CME; sin 2025-07→hoy. Journal 2026 NO usable aquí.
- Journal Notion no guarda hora de entrada → no se puede validar clasificación horaria contra tus trades reales.
- Bias NY AM/PM usa ventanas UTC fijas existentes (12–15, 19–22) y estructura M5 — aproxima tu marcado visual.

## Anexo 2026-10-26 — Sensibilidad horaria (fijada antes de correr)
CDMX tuvo horario de verano hasta 2022-10-30 → antes de 2022-11-01 mi ventana UTC−6 fija está desfasada 1 h en abril-octubre. Sensibilidad: mismo V12 sin cambios, solo operaciones con entrada ≥ 2022-11-01. Misma hipótesis primaria A > B+C. Una corrida (+1 tests múltiples). No cambia parámetros.
