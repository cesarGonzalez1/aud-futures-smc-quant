---
name: preregistrar-hipotesis
description: Prepara una hipótesis de estrategia con SPEC antes de correr el backtest. Usar cuando se quiera probar una idea nueva o una variante (V17, etc.).
---
1. Lee `PROGRESS.md` y confirma que la idea no se probó ya. Si se parece a algo previo, dilo.
2. Crea `SPEC_Vxx.md` con: hipótesis en una frase, qué cambia vs. la versión anterior (SOLO una cosa), parámetros fijos, métrica primaria, regla de aceptación con números, qué se reporta (n, IC95, costos reales, por año, slippage 0/1/2).
3. Si hay calibración, hazla con otros datos (otro año) y fija el criterio antes de ver el hold-out.
4. Crea `backtest/run_vxx.py` copiando la versión previa; test mínimo en `tests/strategy/`.
5. Anota en `PROGRESS.md` que quedó preparada. NO corras el backtest hasta que César lo pida; se corre UNA vez.
