# Módulo `features/` — Feature engineering (Fase 2)

Consume el Parquet crudo validado de `data/` (Fase 1) y produce un dataset
derivado con features, escrito en `data/features/AUDUSD/H1/` con manifest cuyo
`parent_sha256` apunta al crudo (trazabilidad, sección 10).

Referencias: CLAUDE.md sección 7; ADR-003 (régimen/volatilidad), ADR-004
(estructura), ADR-005 (cross-asset), sección 11 (DST), sección 6.1 (look-ahead).

> **Rol = proxy (ADR-006).** Todos los features de estructura intradía (swings,
> sweeps, sesiones) se calculan sobre **AUD/USD spot (Dukascopy)**, que es el
> `proxy` del activo real 6A, no el 6A directamente. El dataset de features hereda
> `role=proxy` en su manifest (lo propaga del crudo del que deriva). Consumidores
> aguas abajo (analysis/reporting) deben tratar estos features como derivados del
> proxy y advertirlo en reportes (ver `reporting/README.md`).

## Componentes

| Archivo | Contenido | Estado |
|---|---|---|
| `indicators.py` | Tendencia/momentum (EMA, MACD, RSI, ADX) + volatilidad (ATR, Bollinger). Librería `ta` (ADR-000) | Implementado |
| `sessions.py` | Sesiones Sídney/Tokio/Londres/NY + solapamiento, DST vía `zoneinfo` (sección 11) | Implementado |
| `structure.py` | Swings (fractal k=2) y liquidity sweeps (ventana 50) point-in-time (ADR-004) | Implementado |
| `realized_vol.py` | Volatilidad realizada (Garman-Klass) + **target** forward N barras (sección 2) | Implementado |
| `cross_asset.py` | XAU/DXY/diferencial de tasas vía `merge_asof` point-in-time (ADR-005) | Implementado |
| `build.py` | Orquestador end-to-end → Parquet de features + manifest | Implementado |

Ejecución: `python -m features.build` (o `make features`).

## Garantías clave
- **Point-in-time (sección 6.1):** todos los features usan solo datos ≤ `t`. Los
  swings se confirman con retraso `k` (un swing centrado en `i` solo se conoce en
  `i+k`), verificado por `tests/features/test_lookahead.py`.
- **Target separado:** `target_fwd_vol_6` usa futuro por diseño (es el label de
  Fase 3), lleva prefijo `target_` y se excluye del test anti-look-ahead.
- **Cada feature** documenta fórmula, fuente y ventana en su docstring.

## Salida (verificada sobre 5 años reales)
36 columnas, 31.179 filas AUD/USD H1. Cross-asset coherente (oro≈3314, DXY≈96,
rate_diff=−0.525), sesiones 37.5% c/u, solapamiento Londres-NY 16.9%, ~4100
swings / ~2200 sweeps.

## Tests (`tests/features/`)
`test_structure.py` (swing/sweep sobre datos sintéticos), `test_sessions.py`
(transición DST), `test_lookahead.py` (point-in-time + confirmación de que el
target sí depende del futuro), `test_realized_vol.py` (ventana forward exacta).

## Pendiente (mejoras, no bloquean Fase 3)
- Volatilidad realizada **por sesión** (7.2 la menciona; hoy es global).
- Integrar un calendario de mercado para etiquetar feriados en huecos (hoy
  quedan como warning genérico en la validación de `data/`).
