# SPEC — validación del agente `lector-capturas` (fijada 2026-11-18, ANTES de probar)
Objetivo: medir si el agente lee bien las capturas antes de usarlo con trades reales.
- **Verdad:** filas de backtest del Notion con imagen (`Gráficas`) y Dirección/Entry/SL/TP ya escritos.
- **Desarrollo (5 capturas):** se usan para ajustar las instrucciones del agente. **Examen (10 capturas):** no se ven mientras se ajusta; se miden UNA vez. Si falla y se ajusta, el siguiente examen usa capturas nuevas.
- **Examen incluye casos difíciles:** días sin trade, captura sin herramienta de posición, etiquetas cortadas. Respuesta correcta = `?`.
- **Se aprueba si:** 0 datos inventados; dirección ≥ 90%; entry+SL+TP exactos ≥ 80% (solo capturas con etiqueta).
- **Calificar:** `python analysis_v16/evaluar_lector.py verdad.csv salida_agente.csv`.
