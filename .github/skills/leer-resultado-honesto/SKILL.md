---
name: leer-resultado-honesto
description: Interpreta resultados de backtest sin sobreafirmar. Usar al revisar un reporte con expectativa, win rate, IC o cortes por grupo.
---
Checklist:
- n total y por corte: < 30 inconcluso; 100-999 preliminar; >= 1000 suficiente.
- Expectativa NETA en R (con costos reales), no bruta. Mira cuánto se come el costo.
- IC95: si cruza 0, la conclusión es "no se puede decir". Nunca "casi positivo".
- Cortes por bucket/trigger/año: son post-hoc. No son hallazgos y no se usan para diseñar la siguiente versión.
- Un año bueno suelto no prueba nada. Mira todas las cohortes.
- Compara con la versión previa y con los resultados reales del journal.
Cierra con una frase y un siguiente paso.
