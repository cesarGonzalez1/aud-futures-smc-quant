# Módulo `data/` — Diseño (Fase 1)

Responsable de la **adquisición, validación y almacenamiento inmutable** de datos
de mercado. Es la única capa que habla con fuentes externas. Todo lo demás
(`features/`, `analysis/`, `reporting/`) consume su salida desde disco y asume el
esquema canónico sin re-validarlo.

Referencias: CLAUDE.md secciones 2, 5, 6.1, 10, 11, 13; ADR-001, ADR-005.

---

## Propósito

Entregar, para cada instrumento del MVP, un dataset OHLCV **reproducible,
versionado y validado**, listo para feature engineering — sin que ningún módulo
aguas abajo tenga que saber de qué proveedor vino ni preocuparse por su calidad.

## Responsabilidad única

Convertir "datos externos heterogéneos" en "Parquet canónico validado + manifest".
No calcula indicadores (eso es `features/`). No analiza (eso es `analysis/`).

---

## Arquitectura interna

```
data/
├── schema.py              # esquema canónico OHLCV + timeframes soportados
├── ingest.py             # orquestador: fetch -> validate -> write (CLI)
├── sources/              # adaptadores de fuente (normalizan al canónico)
│   ├── base.py           #   DataSource (ABC) — contrato común
│   ├── dukascopy.py      #   precio AUD/USD, XAU/USD (ADR-001)  [skeleton]
│   ├── stooq.py          #   DXY diario (ADR-005)               [skeleton]
│   └── rates_table.py    #   diferencial RBA/Fed curado (ADR-005)
├── validation/
│   └── quality.py        # chequeos de calidad -> QualityReport
└── storage/
    ├── manifest.py       # Manifest (sha256) — versionado (sección 10)
    └── parquet_store.py  # escritura/lectura Parquet + manifest
```

Comunicación entre módulos: **solo por archivos en disco** (Parquet/JSON), nunca
por estado compartido en memoria (sección 5). Esto permite reemplazar cualquier
pieza sin romper las demás.

---

## Contratos (inputs / outputs)

### `DataSource.fetch(symbol, timeframe, start, end) -> DataFrame`
- **Input:** símbolo del proyecto, timeframe (`H1`/`D1`), rango UTC tz-aware.
- **Output:** DataFrame en **esquema canónico** (`schema.py`):
  - Índice `timestamp`, UTC tz-aware, ordenado ascendente, sin duplicados.
  - Columnas `open, high, low, close` (requeridas); `volume`, `spread` si la
    fuente los provee (Dukascopy sí; Stooq/DXY no).
- **Responsabilidad del adaptador:** toda la traducción del formato del proveedor
  al canónico + normalización a UTC ocurre aquí, no fuera.

### `quality.validate(df, timeframe) -> QualityReport`
- **Input:** DataFrame candidato + timeframe.
- **Output:** `QualityReport(errors, warnings)`. `is_valid == not errors`.
- **Regla:** un dataset con `errors` **no se escribe** — no es "raw validado".

### `parquet_store.write_dataset(...) -> Manifest`
- **Output en disco:** `data/raw/<symbol>/<timeframe>/data.parquet` + `manifest.json`.
- El `manifest.json` (sección 10) contiene `sha256`, `date_range`, `row_count`,
  `download_timestamp`, y `parent_sha256` (para derivados). La identidad de versión
  de un dataset **es su sha256**.

---

## Flujo de ingesta (`python -m data.ingest`)

```
config/settings.yaml
        │  (símbolos, timeframes, rango, umbrales de calidad)
        ▼
  para cada (source, symbol, timeframe):
        fetch ──► validate ──► [is_valid?] ──► write (parquet + manifest)
                                   │ no
                                   ▼
                          reportar y NO escribir
        ▼
  resumen legible por instrumento
```

El `download_timestamp` se lee del reloj **una sola vez** por corrida y se propaga
a todos los manifests → una corrida es trazable a un instante.

---

## Casos de fallo (y cómo se manejan)

| Fallo | Manejo |
|---|---|
| Fuente no integrada (skeleton) | `NotImplementedError` → `IngestResult(ok=False, "pendiente")`, no aborta el resto |
| Símbolo/timeframe no soportado por la fuente | `ValueError` explícito (no se asume default) |
| Dataset con huecos intradía | error de calidad → no se escribe |
| Hueco de fin de semana (forex) | warning esperado, se escribe |
| Outlier de precio | warning (puede ser evento real); decisión de descartar es humana |
| Parquet alterado fuera del pipeline | `manifest.verify()` falla → dato inválido (test de reproducibilidad) |
| Tabla de tasas con decisión faltante | `validate_completeness` marca hueco largo |

---

## Estado de implementación

| Pieza | Estado |
|---|---|
| `schema.py`, `quality.py`, `manifest.py`, `parquet_store.py`, `rates_table.py`, `ingest.py` | **Implementado** (lógica pura, testeada) |
| `sources/dukascopy.py` | **Implementado** — `dukascopy-python`, BID+ASK→spread (ADR-001). AUDUSD, XAUUSD, DXY. Verificado end-to-end con datos reales |
| `sources/stooq.py` | **Implementado** — URL + PoW solver. Respaldo; DXY usa Dukascopy nativo (ADR-005). Bloqueado desde IPs de datacenter |
| `data/raw/rates/rba_fed.csv` | **Poblado con datos reales** — RBA oficial + Fed (registro FOMC), 34 filas |

**Ejecución real de Fase 1:** `python -m data.ingest` descarga la ventana de 5
años de `config/settings.yaml`. Advertencia: son muchas barras H1 (BID+ASK por
instrumento); la descarga completa tarda varios minutos y genera Parquets grandes.
La verificación se hizo con una ventana corta (2 meses) confirmando el pipeline
completo; la corrida de 5 años es el pull de datos productivo.

---

## Tests (sección 13)

`tests/data/` — corre con `make test`:
- `test_quality.py` — cada chequeo detecta su defecto sobre datos de juguete.
- `test_manifest.py` — roundtrip, detección de manipulación, reproducibilidad por hash.
- `test_rates_table.py` — diferencial, completitud, merge point-in-time.

## Extensiones futuras
- Nuevo activo/timeframe: agregar entrada en `config/settings.yaml` (Fase 6+).
- Nueva fuente: implementar `DataSource`, registrar en `ingest.SOURCES`, y **crear
  un ADR** antes de usarla (regla sección 16).
- Mineral de hierro: pospuesto hasta hallar fuente gratuita confiable (ADR-005).
