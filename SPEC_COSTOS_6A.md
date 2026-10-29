# SPEC COSTOS 6A — modelo de costo real (fijado 2026-10-28)

Origen: datos del usuario (Tradovate / Apex, cuenta 50k). Propuesto antes de aplicarlo a los trades V14 (la vista previa se hizo con los de V13, solo para ver el efecto del costo).
- Contrato 6A estándar: 1 pip (0.0001) = $10; tick (0.00005) = $5.
- Comisión: $3.54 ida y vuelta por contrato (usuario). Usa órdenes LIMIT; siempre 6 contratos.
- Modelo: entrada y TP a limit sin costo adicional; salidas por stop pagan slippage. Slippage desconocido → se reporta 0, 1 (referencia) y 2 ticks.
- costo_R = (comisión + slippage_usd) / (risk_pips × $10). El R se normaliza por contrato, así que 6 contratos no lo cambia.
- Supuestos optimistas conocidos (NO modelados): (1) el limit de entrada siempre se llena; (2) el TP se llena apenas el precio lo toca. Ambos favorecen al backtest.
- Regla del usuario: pérdida máxima por trade ≈ $500 con 6 contratos → riesgo ≤ 8.3 pips. Se reporta como SENSIBILIDAD ("solo trades con riesgo ≤ $500"), no como filtro de la corrida registrada.
- No es una prueba nueva: mismas 192 operaciones de V14, solo cambia el costo. Script: `analysis_v14/costos_reales.py`.
