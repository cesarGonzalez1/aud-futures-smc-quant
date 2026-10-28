# SPEC V14 — NY PM como información, no como puerta (fijada 2026-10-28, ANTES de correr)

## Origen
- Hold-out de etiquetas 2026 (SPEC_V13 §4): NY AM 77.7%, 4H 64.9%, D1 53.8% → aceptados. NY PM (`pm_A`) 47.8% < 50% → no es proxy válido.
- Decisión del usuario (2026-10-28): NY PM NO es puerta de entrada; se usa como información. Se opera aunque NY PM no coincida y se analiza después, como en su journal.
- No se mira P&L para esta decisión (motivo: acuerdo con etiquetas + criterio del usuario).

## Regla V14 (única diferencia con V13)
- **Puerta de bias:** D1-B, H4-B y NY AM S-B (`ny_am`) los tres no neutrales y de la MISMA dirección → se opera en esa dirección. Si no, no se opera. (Decisión mía, fijada aquí: 3 de 3; el usuario no especificó el umbral. No se prueban 2 de 3 ni variantes.)
- **NY PM (`pm_A`, informativo):** se registra por operación como `pm_rel` = a favor / neutral / en contra del lado operado, y `n_aligned` = 3 (PM no coincide) ó 4 (PM coincide). No filtra ni elige nada.
- Todo lo demás idéntico a V12/V13: sweep, IFVG ≤12 velas M5, SL = extremo del sweep (mín 0.3×ATR), TP RR 1.7 acotado 1.6–1.8 por zonas, 1 trade/día, buckets por hora de entrada (A0/A/B/C), `candle_aligned` con D1-B, costos `apply_costs`.
- Reglas de bias ya validadas, sin cambios: D1-B, H4-B, NY AM S-B (SPEC_V13 §3).

## Evaluación
- **Primaria (limpia): operaciones con entrada ≥ 2026-01-01.** Datos que ninguna regla vio. Hipótesis única: expectancy(A) > expectancy(B+C). n<30 → inconclusa (ADR-009).
- **Descriptiva (NO prueba):** entradas < 2026-01-01. V13 ya vio esos datos (P&L incluido); se reporta solo para contexto.
- Descriptivo (sin elegir ganador): tabla por `pm_rel`, por bucket, por trigger, por `candle_aligned`.
- Una sola corrida registrada. Tests múltiples: V13 = 1, V14 = 1 (acumulado en PROGRESS.md).
- Prohibido tras ver resultado: cambiar umbral de la puerta, horas, RR, parámetros. Cambiar algo = versión nueva.

## 4H (explicación del usuario, 2026-10-28) — NO entra en V14
4H funciona como 1H: zonas de interés (liquidez) + tendencia; en tendencia alcista busca un CHoCH para tomar liquidez y seguir alcista; es LATERAL si hay muchas velas sin HH ni LL (EQL/EQH), ~3–5 días. V14 usa H4-B (ya aceptado en hold-out). Candidato futuro `h4_C` = H4-B pero 0 si no hubo ruptura de estructura en los últimos N días (N fijo=4, punto medio de 3–5, sin ajustar), a calibrar por acuerdo en 2024 y revisar en 2026 en una versión posterior, no mezclado con V14.
