# Módulo `analysis/` — Detección de régimen y validación (Fase 3)

Consume el dataset de features (proxy AUD/USD H1, `role=proxy`, ADR-006), detecta
el régimen por reglas y valida su valor predictivo sobre el target de volatilidad
futura. Escribe un experimento autocontenido (sección 12).

Referencias: CLAUDE.md ADR-003 (+ enmienda Fase 3), secciones 2, 6.2, 6.4.

## Componentes

| Archivo | Contenido |
|---|---|
| `cohorts.py` | Segmentación por año calendario (sección 6.4) |
| `regime.py` | `regime_trend` (ADX con histéresis 27/23 + pendiente EMA50), `regime_vol` (percentil móvil ATR14 90d), `regime` combinado |
| `validation.py` | Kruskal-Wallis por cohorte + epsilon² + baseline de persistencia (Spearman) + FDR (Benjamini-Hochberg) |
| `garch_baseline.py` | Baseline GARCH(1,1) (`arch`): pronóstico de vol N-barras + validación del régimen sobre el residual |
| `run.py` | Orquestador régimen vs persistencia → experimento |
| `run_garch.py` | Orquestador régimen vs GARCH(1,1) → experimento separado |

Ejecución: `python -m analysis.run` (o `make analyze`).

## Enmienda ADR-003 implementada (anti-tautología)
- **Baseline de persistencia**: Spearman(vol realizada actual, target). El régimen
  solo aporta si supera esta persistencia — evita concluir valor donde solo hay
  clustering de volatilidad.
- **Tamaño de efecto** epsilon² (no solo p-value) + **FDR** sobre cohortes.
- **Histéresis** en el régimen de tendencia (banda ADX 27/23) contra whipsaw.
- **N mínimo** por celda régimen×cohorte (default 100), se reporta lo descartado.

## Resultados (2020-2025)
- **vs persistencia (Spearman):** régimen de vol significativo en todas las
  cohortes, pero baseline de persistencia fuerte (0.26-0.49) → sospecha de
  tautología. Régimen de tendencia débil/inestable (solo 2020 sobrevive FDR).
- **vs GARCH(1,1) (residual):** el régimen de vol **sigue significativo sobre el
  residual GARCH en las 6 cohortes** (p_fdr < 5e-5) → aporta información más allá
  de GARCH, no es mera persistencia; **pero efecto pequeño** (epsilon² 0.005-0.053).
  Limitación: GARCH in-sample por cohorte (no walk-forward).

Hallazgos honestos, no inflados. Ambos experimentos quedan en `experiments/`.

## Advertencia de proxy (ADR-006)
Todo el análisis usa el proxy spot AUD/USD, no el futuro real 6A. La salida de
`run.py` y el experimento incluyen esta advertencia; los reportes de Fase 3 deben
propagarla (ver `reporting/README.md`).

## Tests (`tests/analysis/`)
`test_cohorts.py`, `test_regime.py` (histéresis, percentil de volatilidad,
consistencia de pendiente), `test_validation.py` (KW, epsilon², N mínimo, FDR).

## Pendiente / próximos pasos de investigación
- GARCH **walk-forward** (el actual es in-sample por cohorte).
- Target direccional secundario (magnitud, nunca signo como señal) — sección 2.
- Cohortes por régimen macro además de año calendario (6.4).
