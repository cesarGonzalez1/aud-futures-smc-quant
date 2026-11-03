---
name: auditar-lookahead
description: Audita una feature o estrategia en busca de uso de datos futuros. Usar al crear o modificar features, señales o la lógica de entrada/salida.
---
1. Para cada columna nueva, di con qué datos se calcula y desde qué timestamp está disponible.
2. Revisa `shift`, `rolling(center=...)`, `merge_asof(direction=...)`, y reindexados.
3. Confirma que la entrada es en la apertura de la barra SIGUIENTE a la confirmación.
4. Corre o agrega el test anti-look-ahead por muestreo (truncar datos en t y comparar el valor).
5. Reporta: columna, riesgo, evidencia, arreglo.
