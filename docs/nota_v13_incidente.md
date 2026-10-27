# V13 — estado y nota de incidente (2026-10-26)

**Corrida V13 registrada (una sola):** 235 ops, neto −0.095R, bruto +0.147R; bucket A +0.058R; sin 2024 ≈ breakeven neto. Bias = reglas del usuario codificadas (D1-B, H4-B, NY AM S-B, NY PM S-A), elegidas por acuerdo con etiquetas Notion 2024 (am_B ~85%, pm ~62%, d1 ~50%, h4 débil n=21).

**Incidente:** sobrescribí `features/bias_user.py` (función `compute_votes`) sin leerlo. Reconstruido y validado contra las salidas guardadas: 2024 oracle 0 difs; confluence.csv 1304 días idéntico salvo 3 días D1 y 4 de dirección (sin operaciones en esas fechas). V13 no se re-corrió.

**Siguiente paso (tuyo):** hold-out con etiquetas 2026:
`python analysis_v13/calibrar_bias.py "<notion_all.csv>" 2026`
Aceptar/rechazar componentes según SPEC_V13 (rechazo si <50% de acuerdo). Después evaluar V13 en 2026. Pendiente: detalle de tu regla 4H (solo 21 etiquetas en 2024) y, opcional, columnas de hora de entrada y tipo de disparador en el journal.
