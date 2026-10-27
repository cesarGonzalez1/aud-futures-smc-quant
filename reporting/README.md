# Módulo `reporting/` — Reporte de estado de mercado (Fase 3, implementado)

Traduce la salida de `analysis/` a reportes Markdown legibles, generados
on-demand (ADR-000). No genera señales de compra/venta.

## Implementación
`report.py` (`python -m reporting.report` o `make report`) lee los features,
calcula el régimen actual, resume la estructura reciente (sweeps), toma la
evidencia del experimento **walk-forward** más reciente como cifra principal, y
escribe `reports/<fecha>_market_state.md` respondiendo las 6 preguntas de abajo.
La advertencia de proxy (ADR-006) va en la cabecera del reporte. Tests en
`tests/reporting/`.

Cada reporte responde (CLAUDE.md sección 8):
1. ¿Qué está pasando en AUD/USD ahora? (régimen, sesión activa)
2. ¿Hay estructura de mercado relevante? (sweeps, swings)
3. ¿Qué evidencia lo respalda? (valores concretos, test de valor predictivo)
4. ¿Qué tan confiable es, y en qué cohorte se basa?
5. ¿Qué cambió respecto al reporte anterior?
6. ¿Qué vigilar a continuación?

## Requisito obligatorio — advertencia de proxy (ADR-006, decidido, aún no implementado)

El activo realmente operado es el **6A** (futuro CME del AUD). La estructura
intradía (swings, sweeps, sesiones) se calcula sobre el **proxy spot AUD/USD** de
Dukascopy, no sobre 6A directamente (que solo se tiene en D1).

Por lo tanto, **cualquier reporte que use datos de estructura intradía debe incluir
una nota visible**:

> "Estructura intradía basada en proxy spot AUD/USD, no en el contrato de futuros 6A
> directamente. El horario de 6A en CME difiere del spot ~24/5, así que sweeps y
> sesiones pueden no calzar 1:1 con la plataforma real de futuros."

Esto se implementa en Fase 3; aquí queda documentado como requisito ya decidido.
