# SPEC V17 — contraste de V16 sobre 6A REAL (fijada 2026-11-15, ANTES de correr)

**Pregunta:** la diferencia entre el backtest manual del usuario (+0.75R) y el motor sobre el proxy AUDUSD (~0R, V15/V16), ¿se explica por el proxy (AUDUSD spot ≠ 6A)?
**Hipótesis nula (esperada):** no. Con el mismo motor sobre 6A real la expectativa neta sigue ~0R.

## Qué NO cambia (copia exacta de V16, `strategy/liquidity_sweep_ifvg_v16.py` con parámetros por defecto)
Puerta V15, bias, confirmación first(IFVG | 3 velas), sweep lookback 50, SL = extremo del sweep + 1 tick, RR fijo 1.7, 1 trade/día, buckets A0/A/B/C, costo real 6A (SPEC_COSTOS_6A, 1 tick en stops, 0 y 2 como sensibilidad). **Ningún parámetro se toca.**

## Qué cambia: SOLO el dato
`6A_ADJ`: 6A real de Databento (ADR-021), M5/H1/D1 con OHLC ajustados por roll (`precio + roll_adj`). D1 agregado por día UTC (igual que el proxy). Sin columna spread (el costo es el modelo real). Periodo 2021-01 → 2026-10 (5.8 años; el proxy llega a 2025-07 en su ingesta original).

## Qué se reporta (mismo formato que V16)
Primaria: expectativa neta en R a 1 tick, n, IC95 bootstrap, costo en R, por año. Primaria secundaria de V16: A > B+C. Sensibilidades predefinidas: slippage 0/2 ticks; riesgo ≤ $500 con 6 contratos; 2026+ aparte.
**Sensibilidad adicional predefinida:** excluir las 23 sesiones donde el contrato rola (00:00 UTC), porque el ajuste de roll es una aproximación (ADR-021). Se reporta junto a la primaria, no la reemplaza.

## Regla de lectura (fijada antes de ver el resultado)
Gate de n (ADR-009): <100 sin conclusión; 100-999 preliminar; ≥1000 suficiente.
- **IC95 cruza 0 →** "sin edge detectable sobre 6A real". El proxy NO explicaba la diferencia con el backtest manual; la hipótesis de sesgo de verlo-ya-hecho en el manual queda más probable. No se afina nada.
- **Límite inferior del IC > 0 →** evidencia preliminar positiva, NO validación: requiere forward test (journal prospectivo) antes de cualquier uso. Aun así n≥100 y 1 sola corrida; Deflated Sharpe no aplica a una corrida única, pero se anota que ya van V13..V17 (5 tests acumulados).
- **Límite superior del IC < 0 →** negativo confirmado preliminar.
Los cortes (bucket, trigger, confirm_type, pm_rel, candle_aligned) son post-hoc: nunca se usan para diseñar V18.

## Comparación con V16-proxy (descriptiva, no inferencial)
Sobre el periodo común (2021-01 → 2025-06) se reportará cuántos días operan ambos, y el acuerdo de lado/ hora. Sirve para entender el proxy, no para elegir ganador.

## Limitaciones declaradas
Continuo por volumen (no el contrato exacto operado); sin bid/ask; roll del 2023-06-18 imperfecto (1 sesión); precio ajustado ≠ precio histórico real (no se usan niveles por precio absoluto en V16, por eso aplica).

## Procedimiento
1. `make prep-6a-adj` (importa DBN + genera `6A_ADJ`). 2. `make test`. 3. `make backtest-v17-humo` (solo ejecuta 1 mes: valida que el código corre; el número se descarta). 4. `make backtest-v17` UNA vez.
Si el paso 3 o 4 falla por un error de código (no por un resultado), se corrige el bug y se anota en PROGRESS; eso no es ajuste de parámetros.
