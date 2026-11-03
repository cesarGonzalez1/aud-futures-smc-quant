# Instrucciones del agente — proyecto 6A (ICT/SMC)

Usuario: César (estudiante de ESCOM/IPN, CDMX UTC-6). Objetivo: cuenta de fondeo Apex 50k operando 6A (futuro CME del AUD) en sesión 6-10 pm CDMX (00-04 UTC).

## Idioma y estilo
- Responde en español, con palabras simples y frases cortas. Sin relleno ni elogios.
- Resultados honestos antes que optimismo. Si algo no se pudo verificar, dilo.

## Lee antes de actuar
1. `CLAUDE.md` (reglas y ADRs) y `PROGRESS.md` (qué ya se probó y qué sigue).
2. Antes de proponer una idea nueva, revisa en `PROGRESS.md` si ya se probó (V1 a V16).
3. Antes de escribir un archivo, revisa si ya existe (`ls`). No sobrescribas sin leer.

## Reglas de investigación (no negociables)
- Todo en UTC. AUDUSD spot (Dukascopy) es PROXY del 6A, nunca el instrumento real.
- Sin look-ahead: un dato en el tiempo t solo usa información disponible hasta t.
- Una hipótesis = un backtest, registrado ANTES de correrlo (`SPEC_Vxx.md`). Cambiar un parámetro después de ver el resultado cuenta como otro test múltiple y se anota.
- Muestra: n < 30 inconcluso; 100-999 preliminar; >= 1000 base suficiente (ADR-009).
- Siempre costos reales de 6A (`analysis_v14/costos_reales.py`, `SPEC_COSTOS_6A.md`): comisión $3.54 ida y vuelta, tick = $5, 1 pip = $10, 6 contratos, riesgo máximo $500.
- Reporta expectativa en R con intervalo de confianza y por cohorte (año). Si el IC cruza 0, di "no se puede decir".
- Cortes post-hoc de un resultado son informativos, nunca hallazgos.
- No inventes datos, fuentes ni APIs. Si algo no está definido, pregunta.

## Comandos
- Entorno: `. .venv/bin/activate` (no uses `python3` suelto).
- Tests: `make test`. Backtests: `make backtest-v16`, etc. Ver `make help`.

## Git
- Commits chicos y claros, a nombre de César. NO agregues `Co-Authored-By` ni trailers de ningún asistente.
- `git pull --rebase` antes de subir. No hagas force push sin que lo pida.
- No subas `data/` ni archivos grandes (están en `.gitignore`).
