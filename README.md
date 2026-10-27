# Plataforma de Análisis Cuantitativo — MVP AUD/USD

Sistema de investigación cuantitativa para AUD/USD intradía. Recolecta y valida
datos reproduciblemente, calcula indicadores clásicos y de estructura de mercado,
identifica el régimen del activo, y genera reportes on-demand con evidencia y
nivel de confianza. **Hasta ADR-014 no era un bot ni generaba señales.** Desde
ADR-015 el objetivo declarado es distinto: codificar la jerarquía discrecional
completa del usuario, validarla con el mismo rigor que las hipótesis
anteriores, y — solo si una versión cruza el gate de validez Y es neta
positiva — construir un motor de señales tipo asistente (Long/Short/No-Trade
con entrada/stop/target, ejecución manual). Ejecución automática (broker) es
una fase posterior explícita, no implícita en este pivote. Ver ADR-015 en
[`CLAUDE.md`](CLAUDE.md).

La especificación completa y vinculante está en [`CLAUDE.md`](CLAUDE.md) (única
fuente de verdad).

## Estado

| Fase | Estado |
|---|---|
| Fase 0 — Diseño, ADRs | Cerrada |
| **Fase 1 — Ingesta de datos** | **En implementación** (ver [`data/README.md`](data/README.md)) |
| Fase 2 — Features | Desbloqueada (ADR-004/005), no iniciada |
| Fase 3 — Análisis de régimen | Desbloqueada (ADR-003), no iniciada |
| Fase 4-6 | Pendientes |

## Estructura

```
config/        Configuración central (settings.yaml)
data/          Adquisición, validación, almacenamiento (Fase 1)  ← activo
features/      Indicadores + estructura de mercado (Fase 2)
analysis/      Detección de régimen + tests (Fase 3)
reporting/     Reportes on-demand (Fase 3+)
experiments/   Experimentos reproducibles (config/results/report)
tests/         Suite pytest (sección 13)
```

## Uso

```bash
make install     # crea .venv e instala dependencias (Python 3.11+)
make test        # corre la suite de tests
make ingest      # corre el pipeline de ingesta Fase 1
```

## Principios (resumen)
- Conocimiento antes que ejecución. La investigación es primero.
- Todo hallazgo se reporta por cohorte temporal; el mercado no es estacionario.
- Dato crudo inmutable, versionado por sha256; todo reproducible desde crudo.
- Ninguna fuente/librería sin ADR aprobado. Ante ambigüedad, se pregunta.
