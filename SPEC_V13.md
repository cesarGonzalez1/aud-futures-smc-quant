# SPEC V13 — bias del usuario codificado + calibración por ACUERDO (fijada 2026-10-26, ANTES de medir)

Motivo: V12 falló en la puerta de bias (algoritmo neutral 46-63% de días, ~30% de acuerdo con tus etiquetas D1).
Objetivo de esta etapa: reproducir TUS etiquetas (Alcista/Bajista/Lateral-Acumulativa), medidas por acuerdo con el journal. NO se mira P&L para elegir reglas.

## 1. Tus reglas (texto del usuario, 2026-10-26)
- D1: compara con la vela del día anterior + estructura. Alcista si: (i) ayer alcista y hoy también y hoy hace HH vs ayer; (ii) ayer bajista, hoy alcista, y la vela bajista de ayer tomó liquidez con claro movimiento alcista después. Espejo = bajista. Si no es claro = lateral.
- 4H: estructura completa (no solo velas).
- NY AM = 6-9 am CDMX = 12:00-15:00 UTC. NY PM = 12-3 pm CDMX = 18:00-21:00 UTC (V12 usaba 19-22: CORREGIDO). Dirección vista en M5.
- Voto "vela previa == hoy": se marca aparte (no es 5º voto).

## 2. Momento de evaluación (point-in-time)
Día de sesión D = fecha CDMX de la fila ("Dia del testing"). T = D+1 00:30 UTC (6:30 pm CDMX). Si D+1 es sábado, T = D 00:30 UTC (fecha ya estaba en UTC; evidencia: precios de entrada de 02-23 y 03-08-2024 calzan con D+0). Solo barras M5 con cierre ≤ T. NY AM/PM del día UTC D.

## 3. Candidatos (definiciones fijas; sin parámetros ajustables salvo los escritos)
Sesión de trading = ancla 17:00 America/Chicago (igual V12).
**D1** — dir(x)=signo(close−open). Y = última sesión completa antes de T; P3 = 3 sesiones previas a Y.
 - D1-A "hoy en desarrollo": hoy = sesión en curso hasta T (high_t, low_t, close_t, open_t); ayer = Y.
 - D1-B "hoy completo": hoy = Y (sesión que cerró ~16:00 CDMX del día D); ayer = la sesión previa a Y; P3 = 3 anteriores a ella.
 Regla (con ayer/hoy según A o B): +1 si (dir ayer>0, dir hoy>0, high_hoy > high_ayer) ó (dir ayer<0, dir hoy>0, low_ayer < min(low de P3), close_hoy > close_ayer). −1 espejo. Si no, 0.
**4H** (H4 desde H1, solo velas cerradas ≤ T):
 - H4-A: `features.bias.add_structure_bias` existente.
 - H4-B: ruptura de estructura (BOS): cierre H4 > último swing high confirmado → +1; cierre H4 < último swing low confirmado → −1; el estado persiste hasta la ruptura contraria.
 (ENMIENDA 2026-10-26, antes de medir acuerdo: el H4-B original era idéntico a H4-A, que ya es 2 máx + 2 mín subiendo/bajando; se sustituye por BOS.)
**NY AM / NY PM** (M5 dentro de la ventana de ese día):
 - S-A: `session_structure_bias` existente (k=2).
 - S-B: movimiento neto close_fin−open_inicio de la ventana; si |neto| ≥ 0.3×(high−low de la ventana) → signo; si no 0.

## 4. Métricas de acuerdo (por componente y candidato)
Etiqueta usuario: Alcista=+1, Bajista=−1, Lateral/Acumulativa=0, vacío = excluida. Reportar: n, cobertura del algoritmo (% no neutral), exactitud 3 clases, acuerdo entre días donde AMBOS no neutrales, tasa de contrario, y baseline (clase mayoritaria).
Regla de selección (fijada): por componente, el candidato con mayor exactitud 3 clases en etiquetas 2024 (train, datos locales hasta 2025-07). Empate → el más simple (A). Hold-out: etiquetas 2026 (159 días) en la máquina del usuario / cuando suba el parquet. Si el acuerdo en hold-out < 50% en 3 clases el componente NO se acepta como proxy.

## 5. V13 (solo después de calibrar)
= V12 con (a) votos D1/4H/NY AM/NY PM de las reglas elegidas, (b) NY PM 18-21 UTC, (c) `candle_aligned` redefinido = dir(ayer)==dir(hoy)==lado con la definición D1 elegida. Resto igual (SPEC_V12). Corrida única registrada; reportar también excluyendo 2024.
