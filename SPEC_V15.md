# SPEC V15 — puerta "al menos 2 a favor y ninguno en contra" (fijada 2026-10-28, ANTES de correr)

## Origen
- V14 (puerta 3 de 3) abre ~19% de los días → ~20 ops/año; el usuario opera ~70/año (2026). Su ledger 2026 (n=68 con etiquetas D1/4H/NY AM): 3 a favor 28 ops (+1.00R); 2 a favor + 1 neutral 15 ops (+0.93R); 2 a favor + 1 en contra 19 ops (+0.16R). "Ninguno en contra" es lo que separa.
- Aviso: patrón visto mirando R del ledger (post-hoc, n chico, 45/70 ops 2026 son backtest manual). La puerta se fija por descripción de su práctica; se prueba sobre datos del motor 2020-2026, que no se usaron para escogerla.

## Regla V15 (única diferencia con V14)
- **Puerta:** entre D1-B, H4-B y NY AM S-B (bias ya validados en hold-out 2026): al menos 2 apuntan al mismo lado y NINGUNO apunta al lado contrario → se opera en ese lado. Cualquier otro caso → no se opera. (3 de 3 y "2 + 1 neutral" abren; "2 + 1 en contra" no.)
- NY PM sigue como información (`pm_rel`). Se registra `gate_tipo` = `tres` / `dos_neutral` por operación.
- **Entrada: SIEMPRE el IFVG posterior al sweep** (regla del usuario, ya implementada): sweep de liquidez en dirección del bias → IFVG M5 dentro de 12 velas M5 → entrada en la apertura de la vela siguiente a la señal IFVG. El tipo de disparador (`eq_vwap`/`eq_extremo`/`sweep_extremo`) solo clasifica el sweep, no cambia la entrada.
- Todo lo demás idéntico a V12/V13/V14 (SL = extremo del sweep con mín 0.3×ATR, RR 1.6–1.8 por zonas, 1 trade/día, ventana 00:30–04:00 UTC, buckets A0/A/B/C).

## Costos
- Se reportan los dos: modelo viejo (`cost_r`) y costo real 6A (SPEC_COSTOS_6A: $3.54 RT/contrato, entrada/TP a limit, 1 tick de slippage en stops; sensibilidad 0 y 2 ticks).

## Evaluación
- **Primaria:** todas las entradas (2020-2026). Hipótesis única: expectancy(A) > expectancy(B+C), con costo real a 1 tick. n<30 por celda → inconcluso (ADR-009).
- Descriptivos (sin elegir ganador): entradas ≥ 2026-01-01 por separado; por `gate_tipo`, `pm_rel`, trigger, `candle_aligned`; sensibilidad "solo riesgo ≤ $500 con 6 contratos".
- Una sola corrida registrada. Tests múltiples acumulados: V13 = 1, V14 = 1, V15 = 1.
- Prohibido tras ver el resultado: cambiar la puerta, horas, RR, parámetros. Cambiar algo = versión nueva.
