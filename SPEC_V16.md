# SPEC V16 — mecánica de entrada del usuario (fijada 2026-10-28/29)

Origen: descripción del usuario con 3 capturas de TradingView (ver claude/descripcion-visual-setup.md) y sus respuestas del 2026-10-28.

## Reglas del usuario codificadas
- **Confirmación:** lo que ocurra primero entre (a) IFVG posterior al sweep, (b) 3 velas M5 CERRADAS seguidas en el sentido de la operación, tras la vela del sweep, dentro de 12 velas M5. Entrada = apertura de la vela siguiente a la señal (≈ cierre de la 3ª vela / del IFVG). "Agresivas" no se codifica (sin parámetro inventado); se queda como atributo a futuro.
- **Sweep:** ocurre ~6:30-8 pm CDMX (ventana 00:30-04:00 UTC, igual que V12). El usuario no marca niveles antes: observa cuándo barre HH/LL cercanos (3 h) o del día, y espera a que termine. No se exige EQ para operar (`trigger_gate=False`); `trigger` queda como atributo (`sweep_interior` si no hay EQ y el nivel está dentro de bandas VWAP).
- **SL:** al final del sweep + 1 tick de 6A (0.00005).
- **TP:** RR fijo 1.7 (sin zonas; el usuario: "un punto donde se cumple el 1.6 o 1.8").
- Bias/puerta: la de V15 (≥2 de D1-B, H4-B, NY AM S-B a favor y ninguno en contra). NY PM informativo.

## Calibración por reproducción del ledger (NO por P&L)
`analysis_v16/reproducir_ledger.py`: para cada trade del ledger se fuerza SU lado y se mide si el motor encuentra entrada ese día. 32 variantes (lookback 50/222 × confirm ifvg/first × trigger_gate × sl_tick × rr). Tolerancia 3 pips.
- **Desarrollo (2024, n=41, backtest manual, datos proxy hasta 2025-07):** encuentra entrada el mismo día: baseline V15 44%; mejor (confirm=first, trigger_gate=False) 63%. "Completo" (entrada y SL ≤3 pips) ≈ 12% en TODAS las variantes → no discrimina (el proxy spot no reproduce precios de 6A: diferencias de ±10 pips sin sesgo constante; stops del usuario en 2024 más cortos, mediana 4.9 vs 7.5 pips del motor). Lookback 222 = 50 (sin efecto); sl_tick y rr casi sin efecto en la reproducción.
- Aviso: la elección de la métrica "encuentra" se hizo después de ver que "completo" no discrimina. El hold-out decide.
- **Variante elegida:** confirm=first, trigger_gate=False, lookback=50, sl_tick=1 tick, rr_mode=fixed 1.7 (las dos últimas por la regla dicha por el usuario, no por la medición).
- **Hold-out (ledger 2026, n≈70, en la máquina del usuario):** `make reproducir-ledger LEDGER=<journal_ledger.csv> YEAR=2026`. Se acepta si `encuentra`(elegida) ≥ `encuentra`(baseline V15) + 10 puntos. Si no, V16 NO se corre.

## Evaluación (solo si el hold-out acepta): `make backtest-v16`, UNA corrida
- Igual que V15 (costo real 6A a 1 tick; primaria A > B+C; descriptivos por confirm_type, gate_tipo, pm_rel, trigger; riesgo ≤ $500).
- Tests múltiples acumulados: V13=1, V14=1, V15=1, V16=1.
