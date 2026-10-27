# CLAUDE.md

# Plataforma de Análisis Cuantitativo — MVP AUD/USD

Versión: 3.2 (Fase 4 — V1/V2/V3/V4; V4 stop en swing H1, ADR-010)
Estado: Fases 1-3 cerradas. Fase 4: 4 hipótesis backtesteadas con costos reales por cohorte, ninguna rentable neta. V4 confirmó el diagnóstico de costo de V3 (stop H1 bajó cost_r 3×) pero el edge bruto se dio vuelta → trade-off, no arreglo. 7 experimentos guardados. Aprendizaje acumulado: señal vive en M5, tensión costo vs reward:risk sin resolver.

---

## 0. Cómo leer este documento

Única fuente de verdad del proyecto. Claude Code implementa sin inventar decisiones ni suponer contexto que no está aquí. Si algo no está definido, **no se asume — se pregunta**.

Esta versión cierra los últimos huecos detectados en la reauditoría de v2.1: método de detección de régimen, definición formal de conceptos de estructura de mercado, tratamiento point-in-time de datos cross-asset, versionado de datos, estrategia de testing y convención de zona horaria.

---

## 1. Misión

(Sin cambios respecto a v2.1.) Construir un sistema de investigación cuantitativa para AUD/USD intradía que recolecta y valida datos reproduciblemente, calcula indicadores clásicos y de estructura de mercado, identifica el régimen del activo, y genera reportes on-demand con evidencia y nivel de confianza. No genera señales automáticas de entrada/salida.

---

## 2. MVP — Alcance de la Fase 1

| Dimensión | Decisión |
|---|---|
| Activo | AUD/USD (forex, spot) |
| Timeframes | H1 (principal) y D1 (contexto) |
| Fuente de datos precio | Dukascopy (ADR-001) |
| Horizonte histórico | 5 años, segmentado en cohortes (6.4) |
| Sesiones | Sídney, Tokio, Londres, NY — con convención de tiempo definida en sección 11 |
| Entregable Fase 1 | Reporte de estado de mercado bajo demanda |
| Fuera de alcance | Multi-activo, ejecución real, paper trading, dashboards en vivo, señales automáticas |

**Pregunta de investigación — resuelta (antes ambigua entre "predictivo" y "no-señales"):**

El sistema **no predice dirección de precio como señal de trading**. El target medible es: **¿el régimen y la estructura de mercado detectados tienen valor predictivo sobre la volatilidad realizada de las próximas N barras H1 (N configurable, default N=6, ≈ una sesión de solapamiento)?** Esto es una métrica estadística verificable (comparar distribución de volatilidad futura entre regímenes), no una señal de compra/venta. Un target secundario opcional, evaluado solo después de validar el primero, es la magnitud del movimiento direccional en esa misma ventana — nunca su signo tratado como señal accionable.

---

## 3. Principios de investigación

(Sin cambios respecto a v2.1: evidencia reproducible, correlación ≠ causalidad, validación OOS obligatoria, explicabilidad, experimentos acumulativos, no-estacionariedad asumida.)

---

## 4. Stack tecnológico y decisiones (ADRs)

### ADR-000 — Lenguaje y librerías base
Python 3.11+ (rango declarado), Parquet+DuckDB, pandas, pandas-ta, scipy/statsmodels, vectorbt, tracking en YAML/JSON+SQLite, reportes en Markdown, sin orquestador, Mac local.

**Actualización (integración Fase 1):** el entorno real de desarrollo es **Python 3.14**, dentro del rango 3.11+ ya declarado y sin incompatibilidades (la suite pasa completa). No se fuerza downgrade a 3.11 solo por el número del documento. Para reproducibilidad del entorno en otra máquina se fija la versión con `.python-version` y `requires-python` en `pyproject.toml`.

**Actualización (inicio Fase 2) — indicadores: `ta` en vez de `pandas-ta`.** `pandas-ta` no instala en Python 3.14 (depende de `numba`, que no ofrece wheel para 3.14, y de `numpy.NaN`, eliminado en numpy≥2.0). Se sustituye por la librería **`ta`** (bukosabino/ta): pura Python, compatible con numpy 2.5, mantenida, y cubre todos los indicadores requeridos por la sección 7 (SMA/EMA, MACD, RSI, ADX, ATR, Bollinger). Es un cambio de una solución madura por otra que sí funciona en el entorno, no una implementación propia (consistente con la Filosofía Tecnológica).

### ADR-001 — Fuente de datos de precio: Dukascopy
Fuente primaria para AUD/USD, XAU/USD. Ver ADR-005 para su rol en cross-asset.

**Decisión de librería (cerrada en Fase 1):** se usa **`dukascopy-python`** (PyPI), NO `duka`.

**Razón:** `dukascopy-python` está mantenida, expone una API limpia (`fetch(instrument, interval, offer_side, start, end)`) que entrega ya un DataFrame con columnas `open/high/low/close/volume`, índice `timestamp` en UTC, y —clave— permite pedir el lado **BID** y **ASK** por separado vía `OFFER_SIDE_BID` / `OFFER_SIDE_ASK`. `duka` se orienta a descarga de ticks crudos y requeriría reimplementar la agregación a H1/D1.

**Spread histórico (requisito de la sección 6.3):** Dukascopy no entrega una columna de spread. El adaptador pide BID y ASK por separado y calcula `spread = ask.close - bid.close` por barra; el OHLCV se toma del lado BID (convención de cotización). Pedir un solo lado NO permitiría modelar costos de transacción, por eso el adaptador **siempre** pide ambos lados.

**Consecuencia:** `data/sources/dukascopy.py` depende de `dukascopy-python`; cada barra descargada incluye columna `spread`. Instrumentos soportados: `AUDUSD`, `XAUUSD` y `DXY` (índice dólar nativo, ver ADR-005).

### ADR-002 — Backtesting: vectorbt
(Sin cambios respecto a v2.1.)

### ADR-003 — Detección de régimen y validación del target predictivo

**Contexto:** "detección de régimen" no estaba operacionalizada; sin método ni definición de qué se predice, la validación es circular.

**Decisión — Fase 3 usa clasificación por reglas/umbrales, no ML, como baseline obligatorio (consistente con la Filosofía ML del proyecto: modelos simples antes que complejos):**

- **Régimen de tendencia:** `trending` si ADX(14) > 25 y pendiente de EMA(50) tiene signo consistente en las últimas K barras; `rango` en caso contrario. Umbral 25 es el estándar de literatura técnica (Wilder) — se documenta como default, no como verdad matemática.
- **Régimen de volatilidad:** ATR(14) actual vs. su percentil móvil de 90 días (mismo timeframe). `alta` si percentil > 70, `baja` si < 30, `normal` en medio.
- **Régimen combinado:** producto cartesiano de los dos anteriores (ej. "tendencia + volatilidad alta"). Se recalcula por cohorte (6.4), nunca con percentiles calculados sobre todo el histórico de una vez (eso sería look-ahead).

**Validación (responde al problema de circularidad):** no se valida "accuracy de clasificación" porque no existe ground truth de régimen. Se valida si el régimen tiene **valor predictivo sobre el target de la sección 2**: para cada régimen, se calcula la distribución de volatilidad realizada en las N barras siguientes, y se compara entre regímenes con un test no paramétrico (Kruskal-Wallis, por no asumir normalidad). Se reporta el resultado **por cohorte** — un régimen puede ser informativo en 2022 y no en 2024, y eso se documenta, no se oculta.

**Alternativas evaluadas:** HMM (Hidden Markov Models) y clustering no supervisado (k-means sobre features de volatilidad/tendencia) son más sofisticados pero no tienen ground truth tampoco, y añaden complejidad sin baseline previo — violan la regla "todo modelo ML necesita un baseline". Se documentan como extensión futura (post-Fase 3), solo si el baseline por reglas resulta insuficiente y se puede demostrar mejora medible.

**Enmienda (inicio Fase 3, resultado de la reauditoría v2.2 — obligatoria antes de declarar válido cualquier resultado de régimen):**

1. **Baseline anti-tautología del target.** Como el régimen de volatilidad usa el percentil de ATR y el target ES volatilidad futura, un Kruskal-Wallis significativo podría ser trivialmente persistencia de volatilidad (la vol clusteriza), no información nueva. Por eso se reporta SIEMPRE, junto al resultado del régimen, un **baseline de persistencia**: la correlación de Spearman entre la volatilidad realizada actual y el target futuro. El régimen solo aporta valor si su efecto no se explica por ese baseline.
2. **Tamaño de efecto + FDR.** Con miles de barras, casi cualquier diferencia da p<0.05. Se reporta el **tamaño de efecto epsilon² de Kruskal-Wallis** (no solo el p-value) y, como las pruebas se corren por cohorte × definición de régimen, los p-values pasan por corrección **Benjamini-Hochberg (FDR)** (6.2).
3. **Histéresis en el régimen de tendencia.** Para evitar whipsaw en el borde ADX=25, se usa una banda (entra a `trending` con ADX>27, sale a `range` con ADX<23) además de la consistencia de pendiente de EMA(50).
4. **N mínimo por celda.** Ninguna celda régimen×cohorte con menos de `min_sample` observaciones (default 100) entra al test; se reporta cuántas se descartaron.

**Definición fijada de volatilidad realizada:** Garman-Klass sobre OHLC (implementado en `features/realized_vol.py`); el target es `target_fwd_vol_6` (vol GK de las próximas 6 barras H1, sección 2). GARCH como baseline más fuerte queda como extensión futura.

### ADR-004 — Definición matemática de conceptos de estructura de mercado (smart money concepts)

**Contexto:** swing high/low, liquidity sweep y zonas de rango/expansión no tienen definición canónica en la industria — sin fijar una, cada implementación es subjetiva y propensa a overfitting (el riesgo más alto identificado en la reauditoría).

**Decisiones (defaults configurables, documentados en `features/README.md`, cualquier cambio de parámetro es un nuevo experimento, no un ajuste silencioso):**

- **Swing high:** barra `i` es swing high si `high[i]` es el máximo estricto entre `high[i-k : i+k+1]`, con `k=2` por default (fractal de 5 barras, convención Bill Williams). Swing low es la definición simétrica sobre `low`.
- **Liquidity sweep:** ocurre en la barra `j` sobre un swing high previo con precio `P` si: (a) `high[j] > P` (penetra el nivel), (b) `close[j] < P` (cierra de regreso adentro, rechazo), y (c) `j` está dentro de una ventana de lookback de 50 barras desde que `P` se formó como swing (para que sea un nivel "reciente" y relevante, no cualquier máximo histórico). Definición simétrica para swing lows con `low[j] < P` y `close[j] > P`.
- **Zona de rango vs. expansión:** se deriva directamente del régimen de volatilidad de ADR-003 (percentil de ATR/ancho de Bollinger): `rango` = percentil < 30, `expansión` = percentil > 70. No se introduce una segunda definición paralela para no duplicar criterios.

**Consecuencia directa sobre overfitting:** como estos parámetros (`k=2`, ventana de 50 barras) son defaults declarados y no calibrados por búsqueda de grid sobre el propio dataset de prueba, cualquier optimización posterior de estos valores debe pasar por el protocolo de control de tests múltiples (6.2) y reportarse con Deflated Sharpe — no se ajustan "a ojo" hasta que el backtest se vea bien.

### ADR-005 — Fuentes cross-asset y tratamiento point-in-time

**Contexto:** DXY, oro, hierro y diferencial de tasas RBA/Fed no tenían fuente aprobada ni tratamiento anti-look-ahead — un hueco real, porque datos macro suelen revisarse retroactivamente.

**Decisiones por serie:**

- **XAU/USD (oro):** Dukascopy lo ofrece directamente con el mismo pipeline que AUD/USD — no se introduce una fuente nueva.
- **DXY (índice dólar):** *[Premisa original]* Dukascopy no lo cubriría de forma nativa confiable, por lo que se aprobó **Stooq** (URL directa `stooq.com/q/d/l/?s=^dxy&i=d`, sin API key, CSV diario) como fuente secundaria.

  **Hallazgo durante integración Fase 1 (dos hechos que corrigen la premisa):**
  1. **Stooq añadió un muro anti-bot** (desafío proof-of-work en JavaScript + POST a `/__verify`). El adaptador `data/sources/stooq.py` lo resuelve automáticamente, pero desde IPs de centro de datos Stooq responde "Access denied" incluso tras resolver el desafío. La descarga automatizada es, por tanto, **frágil**.
  2. **Dukascopy SÍ ofrece un índice dólar nativo** (`INSTRUMENT_IDX_AMERICA_DOLLAR_IDX_USD`), verificado devolviendo datos correctos (≈102 en ene-2024). Esto invalida la premisa original de que Dukascopy no lo cubría.

  **Decisión (confirmada por el usuario):** DXY usa el índice dólar **nativo de Dukascopy** (mismo pipeline, mismo adaptador, sin segunda fuente ni muro anti-bot). `config/settings.yaml` tiene `source: dukascopy` para DXY. El adaptador Stooq (`data/sources/stooq.py`) queda implementado y disponible como respaldo si en el futuro se quiere una fuente independiente para validación cruzada, pero no es la ruta activa.
- **Mineral de hierro:** **se pospone, no entra al MVP.** No existe una fuente gratuita con calidad e historial confiable de 5 años para esta serie. Se documenta como backlog en vez de forzar una fuente de mala calidad — consistente con "gratuita pero confiable" (no solo gratuita).
- **Diferencial de tasas RBA/Fed:** tabla curada desde fuentes oficiales, con una fila por fecha en que cambió cualquiera de las dos tasas (ambos valores forward-filled): `fecha_efectiva`, `tasa_RBA`, `tasa_Fed`, `fuente_url`. **Point-in-time-safe por naturaleza:** una decisión de tasa anunciada no se revisa retroactivamente, así que no hay look-ahead uniendo por la fecha de efectividad real (merge-asof, nunca fecha futura).

  **Estado (Fase 1):** tabla real poblada en `data/raw/rates/rba_fed.csv` (34 filas, 2019-12 → 2025-05). RBA obtenido de `rba.gov.au/statistics/cash-rate/`. **FRED (`fredgraph.csv`) resultó inaccesible desde este entorno**, así que las tasas Fed se compilaron del registro público de decisiones FOMC (`federalreserve.gov`), usando el punto medio del rango objetivo. La correctitud de valores se verifica por spot-check contra fuente oficial (test dedicado); los "huecos" largos entre filas son holds legítimos (ej. era de tasa cero nov-2020 → mar-2022), no decisiones faltantes.

**Regla general de integración (cierra el hueco de look-ahead en macro):** toda serie cross-asset se incorpora al dataset principal vía `merge_asof` sobre su timestamp de publicación/efectividad real, extendiendo el mismo test anti-look-ahead de 6.1 a estas columnas. Ninguna serie cross-asset se actualiza "a mano" sin pasar por el mismo mecanismo de manifest de versión que las demás (sección 10).

### ADR-006 — Activo real (6A futuro CME) vs. proxy spot (AUDUSD)

**Contexto:** el usuario opera realmente el **6A** (futuro CME del dólar australiano), no el AUD/USD spot. Todo lo ya construido en Fase 1 (adaptador Dukascopy, tabla RBA/Fed, manifest/sha256, 15 tests) sigue válido; lo único que cambia es cómo se etiqueta y usa el AUD/USD spot dentro de la arquitectura: de "activo principal" pasa a **proxy documentado**.

**Investigación previa (real, no asumida):** se consultó `6A=F` vía `yfinance` — 1635 barras diarias, **2019-01-02 → 2025-07-01, sin huecos > 7 días, cubre el rango 2020-2025 completo**. El ticker `F*6A.CME` no existe (delisted).

**Decisiones:**
- **Activo real operado:** `6A` (futuro CME del AUD), rol `real`.
- **D1 del activo real:** Yahoo Finance, ticker `6A=F`, vía `yfinance` (`data/sources/yahoo_futures.py`). Nueva fuente aprobada.
- **H1 (estructura intradía):** se REUTILIZA el AUDUSD spot de Dukascopy ya construido, re-etiquetado como `proxy` (nunca como el instrumento real). No se reconstruye nada.

**Alternativas evaluadas para el D1 del real:**
- *Quandl/Nasdaq Data Link*: descartado — discontinuó el acceso gratuito a datos CME.
- *FirstRateData / Databento / Portara*: descartados — de pago.
- *Yahoo Finance (`6A=F`)*: gratuita, cubre el rango completo verificado; elegida.

**Limitaciones conocidas (documentadas, no ocultas):**
1. **Horario de trading distinto:** el 6A en CME (pausa diaria de mantenimiento, huso de Chicago) no coincide con el ~24/5 del spot forex. Los sweeps y sesiones detectados en el **proxy** pueden no calzar 1:1 con la plataforma real de futuros. Todo reporte de estructura intradía debe advertirlo (ver `reporting/README.md`).
2. **Back-adjustment retroactivo:** la serie continua de futuros de Yahoo (`6A=F`) puede REVISAR valores históricos en cada rollover de contrato. Por eso 6A **no es tan inmutable** como el resto: cada descarga se versiona con su propio manifest/sha256 (mismo mecanismo). Si un pull nuevo da un hash distinto al anterior para el mismo rango, es un **cambio esperado (rollover), no un error de calidad**.

**Consecuencia sobre el esquema:** se añade el campo `role` (`real`/`proxy`/`context`) al manifest (`data/schema.py`). AUDUSD=`proxy`, 6A=`real`, XAUUSD/DXY=`context`. La validación de calidad de 6A usa el calendario **CME_FX** (`pandas_market_calendars`), no la heurística de fin de semana del forex.

### ADR-007 — Hipótesis de estrategia V1 (liquidity sweep + Inverse FVG)

**Contexto:** primera regla de trading formalizada, derivada del análisis de Fase 3, para probar en Fase 4. Es una hipótesis **exploratoria**, no una validación definitiva.

**Lógica exacta:**
- **Bias del día:** dirección del régimen de tendencia D1 (ADR-003) al cierre del día anterior. `trending` con pendiente EMA(50)>0 → bias alcista; <0 → bajista; `range` → sin bias (no opera).
- **Puntos de interés (V1, acotado):** PDH/PDL (máximo/mínimo del día calendario anterior, UTC) y máximo/mínimo acumulado de la sesión de Tokio en curso. **Deferido a V2 (backlog explícito, NO implementar ahora):** order blocks y zonas de liquidez más amplias.
- **Ventana de sesión:** 00:00–04:00 UTC (arranque Tokio), configurable.
- **Trigger 1 (H1):** sweep (definición exacta ADR-004) sobre PDH/PDL o sobre el high/low de sesión, en dirección consistente con el bias — bias bajista → solo sweep de máximos; alcista → solo sweep de mínimos.
- **Trigger 2 / confirmación (M5):** Inverse FVG (anexo abajo) en dirección del bias, dentro de una ventana de lookback configurable tras el sweep H1 (default 12 barras M5 ≈ 1 h).
- **Entrada:** apertura de la barra M5 SIGUIENTE al cierre de la barra que confirma el IFVG (nunca en la misma barra que confirma — no usar su cierre como precio de entrada retroactivo).
- **Stop-loss:** más allá del extremo de la mecha que generó el sweep.
- **Take-profit:** swing opuesto más cercano en H1 (estructura, no ratio fijo).
- **Gestión (supuesto default):** una posición a la vez, sin pirámide.

**Anexo (extiende ADR-004) — FVG e Inverse FVG en M5:**
- **FVG de 3 velas** (índices i-1, i, i+1): **alcista** si `low[i+1] > high[i-1]` (zona = `[high[i-1], low[i+1]]`); **bajista** si `high[i+1] < low[i-1]` (zona = `[high[i+1], low[i-1]]`).
- **Filtro de tamaño mínimo:** amplitud del gap ≥ fracción configurable del ATR(M5), default **0.1×ATR** (default declarado, no verdad fija).
- **Inverse FVG:** una vela M5 posterior cierra **más allá del límite opuesto** de una FVG existente, invalidándola. Alcista→IFVG bajista si un cierre posterior < `high[i-1]`; bajista→IFVG alcista si un cierre posterior > `low[i-1]`. Esa vela de cierre es la señal de confirmación.

**Gestión de tests múltiples:** este es UN backtest de UNA hipótesis predefinida → NO se aplica Deflated Sharpe todavía. Si DESPUÉS de ver resultados se ajusta cualquier parámetro (tamaño mínimo FVG, ventana de confirmación, umbrales), eso activa el control de tests múltiples (6.2) y debe reportarse.

### ADR-008 — Hipótesis de estrategia V2 (Acumulación–Manipulación–Distribución)

**Contexto:** V2 extiende ADR-007 (no lo reemplaza; V1 queda intacto y comparable). Añade una fase de acumulación como precondición dura y amplía los puntos de interés. Sigue el esquema AMD (Accumulation–Manipulation–Distribution).

**Fase de Acumulación (NUEVA, precondición dura):** ventana de al menos `M=6` velas H1 consecutivas (configurable) con `regime_vol` ∈ {baja} o régimen de tendencia `range` (ADR-003) inmediatamente antes de la sesión de Tokio. El **rango de acumulación** = `[mín(low), máx(high)]` de esa ventana, que se vuelve un POI adicional.

**POI ampliados (niveles barrible en la manipulación):**
- Rango de acumulación (arriba).
- PDH/PDL (ADR-007) y **PWH/PWL** (máximo/mínimo de la semana calendario anterior).
- **Equal highs/lows:** ≥2 swings (definición ADR-004) dentro de una tolerancia `0.1×ATR`, en una ventana de lookback configurable.
- **Order blocks** (definición en anexo ADR-004 abajo), solo si no están mitigados.

**Fase de Manipulación (= sweep, ADR-004):** ahora exige AMBAS condiciones (obligatorias, no alternativas): (a) acumulación válida según arriba, Y (b) dirección del sweep consistente con el bias del día D1 (ADR-007).

**Fase de Distribución:** sin cambio respecto a V1 — confirmación IFVG en M5, entrada en la apertura de la barra siguiente al cierre de confirmación, stop más allá de la mecha del sweep, target = swing opuesto en H1.

**V2 es UNA única hipótesis predefinida, no una búsqueda de variantes — se registra completa antes de correr el backtest, no se ajusta después de ver resultados.** Mismo régimen de tests múltiples que ADR-007: sin Deflated Sharpe para esta corrida única; cualquier ajuste posterior de parámetros lo activa (6.2).

**Anexo (extiende ADR-004) — Order Block:**
- **Desplazamiento:** `K` velas H1 consecutivas (default configurable) cuyo rango acumulado ≥ `1.5×ATR` y que rompen el swing opuesto más reciente (swing según ADR-004).
- **Order block:** la última vela de color contrario (bajista antes de un desplazamiento alcista, o alcista antes de uno bajista) inmediatamente previa a la primera vela del desplazamiento. Zona = rango completo `[low, high]` de esa vela.
- **Mitigación:** el OB deja de ser válido la primera vez que el precio **cierra a través de él**; un OB mitigado no cuenta como POI vigente.

### ADR-009 — Recalibración de la mecánica a M5 (extiende ADR-007/008)

**Contexto:** V1/V2 detectan la estructura (swing, sweep, order block, acumulación, equal highs/lows) en H1. Los setups tipo liquidity-sweep/AMD ocurren en 1-5 min; una vela H1 diluye la manipulación (el barrido y el rechazo caben dentro de una sola barra H1 y se pierden). V3 recalcula TODA la mecánica de estructura sobre **M5**, usando el dataset M5 ya ingerido y validado (373.936 filas), **sin nueva ingesta**.

**Diseño multi-timeframe deliberado (qué cambia y qué NO):**
- **Mecánica de entrada → M5:** swing, sweep/manipulación, order block, rango de acumulación, equal highs/lows, y la confirmación IFVG. Todo en M5.
- **Contexto de fondo → se mantiene en H1/D1:** régimen de tendencia/volatilidad (ADR-003) y bias del día (ADR-007) siguen en D1/H1. H1/D1 responde "¿qué tipo de día es?"; M5 responde "¿dónde entro exactamente?".
- **IFVG en M5** (mismo timeframe que la estructura ahora). NO se añade M1 todavía — no meter dos variables a la vez; backlog explícito si M5 solo no alcanza n≥100.
- **Sesión Tokio 00:00–04:00 UTC sin cambio**, deliberadamente, para aislar si el problema de V1/V2 era el timeframe o la sesión.

**Parámetros:** se mantienen los defaults de ADR-004/008 (fractal k=2, ventana de sweep 50 barras, desplazamiento 1.5×ATR, etc.) con el MISMO valor numérico — no se recalibran a ojo. Nota: 50 barras en M5 = 250 min (vs 50 h en H1); es el mismo default declarado, y cualquier ajuste pasa por control de tests múltiples (6.2), no antes.

**Gate de validez (declarado ANTES de ver el resultado, no se ajusta después):**
- **< 100 operaciones totales:** "muestra insuficiente para cualquier conclusión" — no se matiza como negativo ni positivo.
- **≥ 100 y < 1000:** "evidencia preliminar, no concluyente".
- **≥ 1000:** base suficiente para una lectura por cohorte con las salvedades habituales.

### ADR-010 — Hipótesis única V4: stop en el swing barrido (extiende ADR-009)

**Contexto:** el diagnóstico de V3 (ADR-009) mostró edge BRUTO positivo (+0.12R) destruido por costos, porque los stops en M5 son tan ajustados (~4.5 pips) que spread+slippage pesan desproporcionadamente al normalizar por R. V4 ataca exactamente eso.

**Cambio (único):** la señal y la entrada de V3 quedan IDÉNTICAS (M5, sin tocar). Solo se redefine el **stop-loss**: de "más allá de la mecha del sweep en M5" pasa a "más allá del **swing H1** del lado barrido". Un stop estructuralmente más amplio reduce `cost_r = costo_precio / riesgo` al aumentar el denominador (riesgo).

**Diseño multi-timeframe (confirmado con el usuario):** mecánica de entrada en M5 (V3), **stop en el swing H1** (más amplio), target sigue en el swing M5 opuesto (V3). El swing H1 vigente se mapea a cada barra M5 con `merge_asof` backward (point-in-time: el último swing H1 confirmado con timestamp ≤ t), extendiendo el anti-look-ahead de 6.1.

**Esto es UNA redefinición motivada por el diagnóstico mecánico de V3, NO una búsqueda de tamaños de stop.** Se implementa solo esta versión; no se prueban múltiples anchos. Igual que V1-V3: hipótesis única predefinida, sin Deflated Sharpe; si tras ver el resultado se ajusta cualquier parámetro (incluido el ancho del stop), eso activa el control de tests múltiples (6.2).

**Detalle:** para un short (sweep de máximos) el stop va por encima del swing high H1 vigente; para un long, por debajo del swing low H1. Si ese swing H1 no está disponible o no queda del lado correcto de la entrada, la operación se descarta (no se cae al stop de mecha — sería otra hipótesis).

---

### ADR-015 — Pivote: jerarquía discrecional completa + motor de señales (asistente, no ejecución)

**Contexto:** hasta ADR-014/V6, este proyecto era investigación exploratoria pura
("no es un bot; no genera señales", sección 15/README). El usuario pidió dos
cambios explícitos: (1) codificar por primera vez su jerarquía discrecional
COMPLETA (no las simplificaciones parciales de V1-V6) y probarla con el mismo
rigor que las hipótesis anteriores; (2) construir, sobre la regla que resulte
válida, un motor de señales tipo "asistente" — evalúa las confluencias y
entrega Long/Short/No-Trade con entrada/stop/target, el usuario ejecuta
manualmente — diseñado para poder escalar más adelante a ejecución automática
(conexión a NinjaTrader/Rithmic), pero esa fase (ejecución) es un ADR nuevo y
posterior, no parte de este.

**Jerarquía codificada (V7, `strategy/liquidity_sweep_ifvg_v7.py`):**
1. Disparadores primarios — EQL/EQH + Liquidity Sweep: idéntico al POI de V5
   (`equal_high_recent`/`equal_low_recent` + sweep).
2. Confirmaciones — MSS y CISD (`features/mss_cisd.py`, NUEVO): MSS = cierre
   rompe el último swing confirmado opuesto; CISD = primer cierre que rompe el
   open de la vela del sweep, en la dirección de la reversión. Se exige AL
   MENOS una de las dos antes de buscar la zona de entrada.
3. Contexto — Demand Zones (= el mismo POI de capa 1, no se reimplementa),
   Quarter Theory (`features/quarter_theory.py`, NUEVO: niveles .00/.25/.50/.75).
   INFORMATIVO, no gate (lección de V2-V5, sección 6.2: sobre-filtrar por
   confluencia adicional reduce muestra sin evidencia previa de que ayude).
   Fibonacci 50-61.8% queda pendiente (falta un origen de swing pair
   point-in-time bien definido — no se aproxima).
4. Zona de entrada — FVG/IFVG: idéntica a V1-V6 (M5), buscada DESPUÉS de la
   confirmación de capa 2 (no en paralelo).
5. Objetivo — BOS y Quarter Theory (`features/liquidity_target.resolve_target_v7`,
   NUEVO): jerarquía de V5 + un nivel Quarter Theory insertado en prioridad 2;
   el swing opuesto (última prioridad, igual V1-V6) ES el BOS.

**SMT pendiente (nota, no ADR-016 todavía):** SMT es divergencia 6A vs 6N; no
hay datos de 6N ingeridos (ADR-006 solo trajo 6A D1). No se aproxima ni se
inventa — V7 opera con 2 de 3 confirmaciones. Ingerir 6N requiere una fuente de
datos nueva (sección 16: toda fuente nueva requiere ADR) — pendiente de que el
usuario lo ejecute en su entorno (limitación de red, igual que el resto del
histórico de ingesta).

**Stop:** heredado de V4/V5 (swing H1 del lado barrido) — mismo supuesto no
especificado por el usuario, para aislar el efecto de las capas 2 y 5 (que sí
son nuevas).

**Resultado real (5 años, 114/114 tests en verde, incluye 12 nuevos):**
**197 operaciones → cruza el gate de 100 (ADR-009), primera versión desde V3 en
hacerlo.** Win rate **52.8%** (el más alto de las 7 versiones). Neto ALL =
**−0.18R** — sigue siendo negativo, pero es la MEJOR expectativa neta de todas
las hipótesis probadas hasta ahora (mejor que V1 −0.27R). Confirmación: CISD
domina (170/197) sobre MSS (27/197). Target: Quarter Theory se usa en 129/197
operaciones, FVG-H1 en 68/197 (ni `day_range` ni el BOS/swing-opuesto se
necesitaron como fallback). **Diagnóstico honesto:** `avg_win` (0.67R) sigue
siendo menor que `avg_loss` (−1.13R) pese al win rate más alto — el nivel
Quarter Theory inmediato (un cuarto = 0.0025) es un objetivo cercano frente a un
stop de swing H1 ancho; el reward:risk sigue en contra. **Hipótesis para
siguiente iteración (no ejecutada todavía, activaría 6.2 si se lee como ajuste
post-resultado):** probar `n_levels=2` en `quarter_target` (saltar un cuarto,
casi una "big figure" completa de recorrido) para equilibrar el reward:risk sin
tocar el stop.

**Fase del motor de señales (asistente):** NO se construye todavía. Regla
explícita de este ADR: el motor de señales solo se activa sobre una versión que
cruce el gate de validez Y sea neta positiva (o al menos aporte evidencia sólida
de valor incremental, con Deflated Sharpe si ya hay múltiples variantes
comparadas — sección 6.2, que aplicaría en cuanto se ajuste algo tras ver este
resultado). Automatizar una regla todavía negativa quitaría la parte emocional
del trader... para perder de forma consistente y sin fricción. Cuando exista una
regla validada, el motor de señales es una CAPA NUEVA y separada (`decision_engine/`,
no reemplaza `strategy/`+`backtest/`): reevalúa la misma jerarquía sobre la
barra más reciente en vez de sobre todo el histórico, y expone un objeto de
señal estructurado (Long/Short/No-Trade + entrada/stop/target + confianza +
qué capa de la jerarquía se activó) — ejecución manual primero; ejecución
automática (NinjaTrader/Rithmic) es una fase posterior explícita, con su propio
ADR y controles de riesgo (kill-switch, tamaño de posición, cumplimiento de
reglas de la cuenta de fondeo), no implícita en este pivote.


### ADR-016 — Ingesta de 6N y divergencia SMT (extiende ADR-015)

**Contexto:** la jerarquía discrecional completa (ADR-015) incluye SMT (6A vs
6N) como una de las confirmaciones de capa 2, junto a MSS/CISD. Hasta ahora se
documentaba como "pendiente" por falta de datos de 6N. Este ADR autoriza e
implementa esa fuente nueva (sección 16: toda fuente nueva requiere ADR + pedido
explícito del usuario — ya solicitado al pedir la jerarquía completa en ADR-015).

**Fuente:** 6N (futuro CME del dólar neozelandés) vía `data.sources.yahoo_futures`
(`YahooFuturesSource`, mismo adaptador que 6A) — `SYMBOL_MAP["6N"] = "6N=F"`.
Registrado en `config/settings.yaml` como `instruments.cross_asset` (role
`context`, `market_calendar: CME_FX`, igual patrón que XAU/DXY, ADR-005).

**Limitación de granularidad (heredada de ADR-006, no nueva):** Yahoo solo
sirve 6A/6N en D1. SMT aquí es una confirmación a nivel D1 (mismo nivel que el
bias HTF de `features.bias`), NO una confirmación M5 como MSS/CISD. Es una
restricción real de la fuente de datos, no una aproximación — se documenta
explícitamente en `features/smt.py`, igual que ADR-005 ya documentó la
limitación de resolución diaria de DXY.

**Definición (`features/smt.py`, point-in-time vía `features.structure.add_structure`
+ `merge_asof` backward, mismo patrón que `features.cross_asset`):**
divergencia bajista (`smt_bear`) = 6A confirma un swing high MÁS ALTO que su
swing high confirmado anterior, Y 6N, en el mismo intervalo, NO confirma un
swing high más alto que el suyo. Simétrico para `smt_bull` (swing lows).

**Estado:** módulo implementado y probado con datos sintéticos (3 tests
nuevos, 119/119 en verde). **La ingesta real de 6N NO se pudo ejecutar en este
entorno** (red sin acceso a `query1/query2.finance.yahoo.com` — mismo tipo de
limitación que ya afectó ingestas anteriores). Pendiente que el usuario corra
`python -m data.ingest` en su entorno para traer 6N y habilitar cualquier
backtest que use `smt_bear`/`smt_bull` con datos reales — hasta entonces, SMT
no se ha integrado a ninguna versión de estrategia (V7-V9 siguen sin SMT, tal
como se documentó en ADR-015).

### ADR-018 — Ampliación de datos: intradía real (M1/M5/H1/H4) + investigación de fuentes gratis

**Contexto:** el usuario pidió, explícitamente, dejar de tratar este proyecto
como el centro (menos apego a las reglas del proyecto por sí mismas) y priorizar
el objetivo real (motor de señales + futuro bot en 6A), incluyendo buscar
activamente cómo se construyen sistemas de trading reales y qué fuentes de
datos gratuitas existen más allá de las 3 ya usadas (Dukascopy, Yahoo D1, Stooq).

**Investigación de fuentes (resumen honesto, no todo es gratis):**
- **Datos reales de 6A intradía multi-año, gratis: prácticamente no existen.**
  Los proveedores profesionales (FirstRateData, Portara/CQG, Databento,
  AlgoSeek) tienen exactamente lo que se necesita (M1/M5/H1/H4, 15-20 años) pero
  cobran (FirstRateData ~$100 USD aprox. por dataset de futuros con historia
  completa — la opción más barata encontrada si en algún momento se decide pagar).
- **Yahoo Finance (yfinance):** YA integrado en el proyecto (ADR-016), pero solo
  traía D1. Sí soporta intradía real de 6A/6N (M1/M5/H1), gratis, pero con
  muy poca profundidad histórica (M1 ~30 días, M5 ~60 días, H1 ~730 días) —
  implementado en este ADR (ver abajo).
- **Interactive Brokers (TWS/IB Gateway API):** la opción gratuita más prometedora
  para HISTORIA REAL más profunda (continuous futures `CONTFUT`, M1/M5/H1/H4,
  potencialmente varios años). Requiere: cuenta de IBKR (paper trading es
  gratis), TWS o IB Gateway corriendo localmente, y posiblemente una
  suscripción de datos de mercado de bajo costo para CME. NO se implementó en
  este ADR — requiere que el usuario abra la cuenta y corra el cliente
  localmente (no accesible desde un sandbox sin GUI); queda como ADR-019
  propuesto si se decide seguir ese camino.

**Implementado en este ADR — `data/sources/yahoo_futures.py` extendido:**
ahora soporta M1, M5, H1 (nativos de yfinance) y H4 (derivado por resample de
H1 — Yahoo no tiene intervalo nativo de 4h), además de D1. Cada límite de
profundidad histórica de Yahoo está documentado explícitamente en el código
(no oculto) y el adaptador RECORTA automáticamente el rango pedido si excede lo
que Yahoo realmente sirve, avisando por consola en vez de fallar en silencio o
fingir tener más historia (sección 16). M1 encadena requests en bloques de 7
días (límite de Yahoo para ese intervalo). `data/schema.py` ganó `M1` y `H4`
en `TIMEFRAME_FREQ`. `config/settings.yaml`: `real_asset` (6A) y el cross-asset
6N ahora piden `["M1", "M5", "H1", "H4", "D1"]` en vez de solo `["D1"]`.

**Por qué esto NO reemplaza el proxy de Dukascopy (ADR-006):** con 30-730 días
de historia real, no alcanza para los backtests de 5 años de V1-V11 — sí sirve
para (a) validar/cruzar que el proxy AUDUSD se mueve igual que el 6A real en el
periodo reciente que se solapa, y (b) alimentar el motor de señales en modo
VIVO (ADR-017), donde solo importa la barra de hoy.

**Estado:** código implementado y probado con datos sintéticos (8 tests
nuevos/actualizados, 129/129 en verde). La ingesta real requiere que el usuario
corra `make ingest` en su entorno (este sandbox no tiene acceso a
`query1/query2.finance.yahoo.com`, confirmado en ADR-016).

**Resultado real (corrido por el usuario, 2026-07-08, ventana solapada
2024-07-14 a 2025-07-01, 5568 barras H1):** correlación de retornos H1 =
**0.9953**, correlación de rango intrabar = **0.9921**, match de swing highs
confirmados (±2h) = **97.5%** (673 swings), match de swing lows = **97.6%**
(701 swings). **Veredicto: ALTA — respalda ADR-006 con evidencia real por
primera vez.** Los 5 años de backtest de V1-V11 sobre el proxy siguen siendo
confiables; no hace falta reconsiderar su peso.

### ADR-019 — Gestión de riesgo (position sizing + frenos de circuito) + score logístico (probado, descartado)

**Contexto:** el usuario pidió investigar qué tienen sistemas de trading que
sí funcionan y que el nuestro no tenía. Hallazgo principal: el proyecto media
todo en R (múltiplos de riesgo) pero JAMÁS calculaba cuánto arriesgar en
dólares reales, ni tenía ningún freno automático tras una racha de pérdidas.
Investigación citada: "~95% de las evaluaciones de cuentas de fondeo fallan
por mala gestión de riesgo, no por estrategias malas" (quantvps.com,
2026-02-16); caso real citado ahí: evaluación FTMO de $100k completada
arriesgando 0.75%/trade y parando tras 2 pérdidas consecutivas.

**Implementado — `decision_engine/risk_manager.py`:**
- `position_size(...)`: tamaño fraccional-fijo estándar — arriesga `risk_pct`
  del equity dado el stop de la señal. Para 6A: `contract_multiplier=100_000`
  (tamaño del contrato CME en AUD). Redondea hacia abajo, nunca fuerza un size
  mínimo que viole el % de riesgo pedido.
- `score_adjusted_risk_pct(...)`: escala el riesgo base (0.75%, el mismo valor
  del caso real citado) según la confianza del `ConfluenceScorer` — más
  confianza, más tamaño (dentro de un rango acotado, nunca cero solo por
  score bajo; el gate de tomar o no el trade ya lo decide `live_signal`).
- `CircuitBreaker`: frenos de circuito — máximo de pérdidas consecutivas
  (default 2, replicando el caso real), pérdida diaria máxima en R, máximo de
  operaciones/día. Separa la SEÑAL (qué operar) del RIESGO (cuánto y si se
  puede seguir operando) — dos capas distintas, igual que cualquier sistema
  institucional.
- `decision_engine/live_signal.py` extendido: `evaluate_latest` ahora acepta
  `account_equity`/`contract_multiplier`/`circuit_breaker` opcionales; si se
  dan, `Signal` incluye tamaño de posición sugerido y si el freno de circuito
  permite operar (una señal puede EXISTIR y aun así marcarse "no operar" si el
  freno está activo).
- `decision_engine/run_signal.py` (CLI, `make signal`) ya muestra el tamaño
  sugerido sobre una cuenta de ejemplo de $50,000.

**Honesto:** con V9 todavía neto negativo (-0.119R), ningún position sizing
hace rentable una estrategia que no lo es — protege el capital y limita
pérdidas mientras se sigue iterando, no genera edge donde no lo hay.

**También investigado y probado — `LogisticConfluenceScorer` (regresión
logística sobre las mismas features, alternativa a `ConfluenceScorer` aditivo):**
validado con la MISMA metodología out-of-sample que el aditivo
(train 2020-2023 / test 2024-2025 de V7). Resultado real: aditivo da -0.059R
en el top 50% por score; el logístico da **-0.354R — peor que no filtrar nada
(-0.271R)**. Con ~135 operaciones de entrenamiento y 5 features categóricas
(~15-20 columnas tras one-hot), incluso con regularización fuerte (C=0.3) el
modelo logístico se sobreajusta. **Se mantiene `ConfluenceScorer` (aditivo)
como score de producción.** La clase queda en el código, documentada como
"probada y descartada por ahora", disponible para cuando haya sustancialmente
más datos (cientos-miles de operaciones, no cientos).

**154/154 tests en verde** (14 nuevos: `test_risk_manager.py` x10, extensiones
a `test_scoring.py` y `test_live_signal.py`).

### ADR-020 — Ingesta manual desde TradingView (CSV)

**Contexto:** el usuario tiene una prueba gratuita de TradingView (Plus/Premium)
con acceso a varias temporalidades y preguntó si se pueden traer datos de 6A
desde ahí. Investigado (fuentes de enero-mayo 2026): TradingView NO tiene API
pública para descargas automatizadas. Sí tiene exportación nativa de CSV
("Download chart data..."), pero es MANUAL, por gráfico, y limitada a
Plus/Premium (10,000 velas por exportación en Plus, 20,000 en Premium,
limitado a lo que esté cargado en pantalla — hay que desplazarse/hacer zoom
out para cargar más historia antes de exportar).

**Implementado:** `data/sources/tradingview_csv.py` (`TradingViewCSVSource`,
registrado en `data/ingest.py`), lee los CSV que el usuario exporta a mano
desde `data/manual_imports/tradingview/` (convención `{symbol}_{timeframe}.csv`,
soporta varios archivos del mismo símbolo/temporalidad con sufijo `__N` para
cuando una sola exportación no alcanza — se concatenan y deduplican). Detecta
automáticamente el formato de tiempo (ISO o Unix, ambos disponibles al
exportar). `data/import_tradingview.py`: script standalone
(`python -m data.import_tradingview 6A H1`) que NO toca `make ingest` ni
`config/settings.yaml` — comando aparte para no arriesgar el pipeline
automático con una fuente que depende de un paso manual del usuario.
Instrucciones completas paso a paso en
`data/manual_imports/tradingview/README.md`.

**Realismo del esfuerzo manual por temporalidad** (documentado explícitamente,
no se oculta): D1/H4 -> 1 exportación cubre años, fácil. H1 -> 1-2
exportaciones para años, fácil. M5 -> ~5-6 exportaciones POR AÑO, tedioso pero
viable. M1 -> impráctico por este método para más de unas semanas —
Interactive Brokers (ADR-018, aún no implementado) sigue siendo mejor camino
para M1 profundo.

**160/160 tests en verde** (6 nuevos: `test_tradingview_csv.py`, con CSVs
sintéticos que imitan el formato real de exportación).

## 5. Arquitectura

```
1. data/       -> Adquisicion (Dukascopy, Stooq, tablas de tasas), validacion, almacenamiento inmutable en Parquet + manifest
2. features/    -> Indicadores clasicos + estructura de mercado (ADR-004) + sesiones + cross-asset (ADR-005)
3. analysis/     -> Deteccion de regimen (ADR-003), tests estadisticos, comparacion entre cohortes
4. reporting/     -> Traduccion de analysis/ a reportes legibles, on-demand
```

Comunicación entre módulos solo por archivos en disco (Parquet/JSON), nunca por estado compartido en memoria.

---

## 6. Metodología concreta

### 6.1 Point-in-time / anti-look-ahead
Todo indicador y toda serie cross-asset se calcula únicamente con datos disponibles hasta el timestamp `t`. Test automático por muestreo, extendido explícitamente a las columnas de ADR-005 (no solo a precio).

### 6.2 Control de tests múltiples
Deflated Sharpe Ratio para resultados tipo estrategia; corrección Benjamini-Hochberg (FDR) para baterías de tests estadísticos independientes, incluyendo cualquier recalibración de los parámetros fijados en ADR-004.

### 6.3 Costos de transacción
Spread histórico (Dukascopy bid/ask) + slippage en función de ATR. Obligatorio para cualquier resultado tipo backtest.

### 6.4 Segmentación temporal (cohortes)
Cohortes por año calendario (2021-2025) como partición mínima, ajustable a regímenes macro conocidos. Todo hallazgo se reporta por cohorte, nunca como verdad general sobre los 5 años.

### 6.5 Validación fuera de muestra
Walk-forward con ventana móvil, respetando orden temporal.

---

## 7. Features — categorías (definiciones formales en ADR-003/004)

1. **Tendencia y momentum:** medias móviles, MACD, RSI, ADX.
2. **Volatilidad:** ATR, Bollinger Bands, volatilidad realizada por sesión.
3. **Estructura de mercado:** swing highs/lows y liquidity sweeps según ADR-004; zonas de rango/expansión según ADR-003.
4. **Sesiones:** Sídney/Tokio/Londres/NY y solapamientos, con convención de tiempo de la sección 11.
5. **Cross-asset:** XAU/USD (Dukascopy), DXY (Stooq), diferencial RBA/Fed (tabla curada). Hierro pospuesto (ver ADR-005).

Cada feature documenta: fórmula exacta, fuente, ventana temporal requerida, y si es un default configurable (todos los de ADR-004 lo son).

---

## 8. Reportes — qué debe responder cada reporte

1. ¿Qué está pasando en AUD/USD ahora? (régimen por ADR-003, sesión activa)
2. ¿Hay estructura de mercado relevante? (sweeps y swings según ADR-004)
3. ¿Qué evidencia lo respalda? (valores concretos, resultado del test de valor predictivo sobre volatilidad futura)
4. ¿Qué tan confiable es esta lectura, y en qué cohorte se basa?
5. ¿Qué cambió respecto al reporte anterior?
6. ¿Qué se debería vigilar a continuación?

No se generan señales de compra/venta.

---

## 9. Documentación — estándar obligatorio

(Sin cambios respecto a v2.1: README por módulo, docstrings con supuestos, type hints, formato ADR fijo, ninguna función inventa fuentes no aprobadas, experimentos autocontenidos.)

---

## 10. Versionado de datos — spec concreto

**Problema que cierra:** "almacenamiento inmutable" y "versión del dataset" se mencionaban sin mecanismo verificable.

**Decisión:** cada dataset crudo o derivado se acompaña de un `manifest.json` en la misma carpeta, con:

```json
{
  "source": "dukascopy",
  "symbol": "AUDUSD",
  "timeframe": "H1",
  "date_range": ["2020-07-01", "2025-07-01"],
  "download_timestamp": "2026-07-01T00:00:00Z",
  "sha256": "<hash del archivo parquet>",
  "row_count": 0
}
```

Ruta convencional: `data/raw/<symbol>/<timeframe>/manifest.json` junto al `.parquet` correspondiente. Toda referencia a "versión de dataset" en un experimento (sección 12) apunta al `sha256` de este manifest, no a una fecha o número de versión informal. Un dataset derivado (features) referencia el `sha256` del dataset crudo del que proviene, permitiendo trazar la cadena completa.

---

## 11. Convención de tiempo y DST

**Problema que cierra:** features de sesión sin manejo de husos horarios ni horario de verano — fuente clásica de bugs silenciosos.

**Decisión:**
- Todo el almacenamiento y cómputo interno se hace en **UTC**, sin excepción. Dukascopy y Stooq se normalizan a UTC en la capa de ingesta (`data/`).
- Las sesiones (Sídney, Tokio, Londres, NY) se definen por su horario local de mercado, y su equivalente en UTC se calcula dinámicamente por fecha usando `zoneinfo` (librería estándar de Python) contra la zona horaria de cada plaza (`Australia/Sydney`, `Asia/Tokyo`, `Europe/London`, `America/New_York`), no con offsets UTC fijos — así el cambio de horario de verano de cada plaza se resuelve automáticamente y de forma independiente entre sesiones (no todas cambian DST el mismo día).
- Se agrega un test específico que verifica, para fechas de transición de DST conocidas, que la barra H1 se asigna a la sesión correcta.

---

## 12. Sistema de experimentos

(Sin cambios de estructura respecto a v2.1: `experiments/<fecha>_<nombre>/` con `config.yaml`, `results.json`, `report.md`. `config.yaml` ahora referencia explícitamente el `sha256` del manifest de sección 10 como identificador de versión del dataset.)

---

## 13. Estrategia de testing

**Problema que cierra:** "cada módulo testeable" no estaba operacionalizado más allá del test anti-look-ahead.

**Decisión:** suite de tests con `pytest`, organizada por módulo, con estas categorías obligatorias:

- **Tests de calidad de datos** (`data/`): el validador de ADR-001 (huecos, duplicados, outliers, timestamps monotónicos) se implementa como funciones de test, no como función suelta que solo imprime warnings — un dataset que falla estos tests no se considera "raw validado".
- **Tests anti-look-ahead** (`features/`, transversal): sección 6.1, extendido a cross-asset.
- **Tests de definición de features** (`features/`): casos sintéticos construidos a mano que verifican que la detección de swing/sweep (ADR-004) da el resultado esperado sobre datos de juguete donde se conoce la respuesta correcta.
- **Test de DST** (`features/`, sesiones): sección 11.
- **Test de reproducibilidad** (transversal): recalcular un resultado desde el dataset crudo referenciado por su `sha256` y comparar contra el resultado guardado — si no coincide, el resultado se considera inválido.

---

## 14. Roadmap por fases (con precondiciones)

- **Fase 0 (cerrada)** — Documento base, ADR-000/001/002.
- **Fase 1 (CERRADA y verificada — 2026-07-01)** — Ingesta real, validación como suite de tests, manifest sha256, tabla RBA/Fed real. **Verificado sobre 5 años (2020-07-01→2025-07-01):** 6/6 targets con errores=0, sha256 verify=True, cobertura 94.7-99.9% de mercado abierto (AUDUSD H1=31.179, XAUUSD H1=29.558, DXY D1=1.293, 6A D1=1.257). El **pivote de ADR-006** (activo real 6A + roles real/proxy/context) se hizo como parte del cierre de Fase 1, no como fase aparte: se añadió la fuente Yahoo (6A=F), el campo `role` en el manifest y el calendario CME_FX de validación, sin reconstruir lo ya hecho.
- **Precondición Fase 2:** ADR-004 y ADR-005 cerrados (ya lo están) + convención DST (sección 11) implementada.
- **Fase 2 (CERRADA)** — Feature engineering según sección 7 (indicadores `ta`, sesiones con DST, estructura ADR-004, volatilidad realizada + target, cross-asset ADR-005). Auditado contra ADR-003/004: swing k=2 y sweep lookback=50 exactos; inputs de régimen (ADX14/ATR14/EMA50) presentes (la regla de régimen es Fase 3). Features marcados `role=proxy` (ADR-006). Cobertura de tests obligatoria completa (definición de swing/sweep, anti-look-ahead, DST). 29/29 tests verdes.
- **Precondición Fase 3:** ADR-003 cerrado (ya lo está en esta versión).
- **Fase 3 (primera corrida CERRADA)** — Detección de régimen por reglas con histéresis (ADR-003 + enmienda), validación de valor predictivo sobre `target_fwd_vol_6` por cohorte, con baseline de persistencia + epsilon² + FDR, y experimento autocontenido (sección 12). **Hallazgo honesto de la primera corrida (2020-2025):** el régimen de volatilidad es altamente significativo pero con un baseline de persistencia fuerte (Spearman 0.26-0.49) — buena parte de su "valor" es persistencia de volatilidad, no información nueva; el régimen de tendencia es débil e inestable entre cohortes (solo 2020 sobrevive FDR, epsilon²≈0.01). La maquinaria de la enmienda (baseline/epsilon²/FDR/por-cohorte) cumplió su función: expuso la tautología y la inestabilidad en vez de sobre-afirmar.

**Baseline GARCH(1,1) (librería `arch`, experimento `2026-07-01_regime_vs_garch`):** se repitió la validación sobre el RESIDUAL de un pronóstico GARCH(1,1) por cohorte. **Resultado:** el régimen de volatilidad **sigue siendo significativo sobre el residual GARCH en las 6 cohortes** (p_fdr < 5e-5 en todas) — es decir, aporta información más allá de lo que GARCH captura, no es mera persistencia. **Pero el efecto es pequeño** (epsilon² sobre residual 0.005–0.053). **GARCH walk-forward (conclusión primaria, experimento `2026-07-01_regime_vs_garch_walkforward`):** se corrigió la asimetría point-in-time del in-sample — GARCH ajustado solo con datos ≤ t, refit semanal (168 barras), ventana expansiva, cobertura 96.8%. **Resultado:** el régimen **sigue significativo sobre el residual walk-forward en las 6 cohortes** (p_fdr_wf < 1e-3) — sobrevivió la prueba más exigente disponible. **Efecto pequeño** (epsilon²_wf 0.002–0.062). El in-sample se conserva como análisis de sensibilidad (no se borra, sección 12). **Conclusión de referencia para reporting:** el régimen tiene valor predictivo real e incremental sobre GARCH walk-forward, pero de magnitud modesta. Limitación restante: GARCH walk-forward expansivo (no ventana móvil); target direccional secundario pendiente.
- **Fase 4 (INICIADA — hipótesis única ADR-007)** — Módulos `strategy/` (liquidity sweep + IFVG, genera operaciones discretas) y `backtest/` (costos: medio spread M5 real + slippage por ATR; métricas por cohorte: win rate, expectancy, maxDD, Sharpe). Soporte M5 añadido al adaptador Dukascopy y features nuevas (FVG/IFVG en `features/fvg.py`, PDH/PDL y niveles Tokio en `features/levels.py`), todas con test anti-look-ahead. **El resultado de este backtest es EXPLORATORIO**: la primera prueba real de una regla derivada del análisis, NO una validación definitiva. Por ser UNA hipótesis predefinida NO se aplica Deflated Sharpe todavía (ADR-007); ajustar cualquier parámetro tras ver resultados activa el control de tests múltiples (6.2). **Decisión de herramienta:** las métricas se calculan directamente sobre las operaciones discretas (no con vectorbt, que está pensado para vectorizar señales sobre series continuas / grillas de parámetros); vectorbt (ADR-002) se mantiene aprobado para cuando haya una grilla que vectorizar. **Decisión de arquitectura:** el bias del día vive en `strategy/` (no en `features/`) porque deriva del régimen (ADR-003, capa `analysis/`) y `features/` no debe depender de `analysis/`; la capa de estrategia compone legítimamente ambas. Walk-forward + Deflated Sharpe entran cuando se pase de esta hipótesis única a exploración de variantes.
- **Fase 4 — corrida V2 (ADR-008, AMD):** V2 añade precondición de acumulación + POI ampliados (rango acumulación, PWH/PWL, equal highs/lows, order blocks), manteniendo V1 intacto (`strategy/liquidity_sweep_ifvg_v2.py`, `backtest/run_v2.py`, experimento `2026-07-02_strat_liq_sweep_amd_v2`). **Resultado exploratorio (proxy 5 años):** V1 = 40 ops, expectancy neta −0.27R; V2 = 49 ops, expectancy neta −0.31R. **Ninguna de las dos es rentable tal cual.** V2 sube ligeramente el win rate (35%→39%) y el nº de señales pero no la expectancy. **Muestra pequeña por cohorte** (2-24 ops): como en V1, más señales NO implica suficiencia estadística — la lectura es tentativa, no concluyente. Desglose por POI guardado para análisis futuro (order blocks generaron la mayoría de señales). Sin Deflated Sharpe (hipótesis única, ADR-008); optimizar parámetros ahora activaría 6.2.
- **Fase 4 — corrida V3 (ADR-009, mecánica en M5):** toda la estructura (swing, sweep, order block, acumulación, equal highs/lows) + IFVG recalculadas en M5; bias/régimen siguen en D1/H1 (`strategy/liquidity_sweep_ifvg_v3.py`, `backtest/run_v3.py`, experimento `2026-07-02_strat_liq_sweep_amd_m5_v3`). **Gate de validez (declarado antes, ADR-009): 245 operaciones → "evidencia preliminar, no concluyente"** (cruzó el umbral de 100 que V1/V2 no alcanzaban por cohorte). **Hallazgo clave — edge bruto positivo destruido por costos:** el R BRUTO medio es **+0.12R** (la mecánica M5 sí tiene sesgo favorable), pero el costo medio por operación es **0.87R** → **R neto −0.76R** (peor que V1/V2). Causa mecánica: los stops en M5 son muy ajustados (riesgo medio ≈ 4.5 pips), así que el spread + slippage (fijos en precio) pesan desproporcionadamente al normalizar por R. **Conclusión:** el timeframe correcto para la señal parece M5 (genera edge bruto y volumen de señales), pero la gestión de riesgo/costo de V1-V3 la hace inviable neta; el próximo paso de investigación es el manejo de costos/stop (ej. stops más amplios, filtro de spread, o instrumentos de menor costo), NO recalibrar la señal. Order blocks siguen dominando los POI (218 de 245). Sin Deflated Sharpe (hipótesis única); optimizar activa 6.2.
- **Fase 4 — corrida V4 (ADR-010, stop en swing H1):** señal/entrada de V3 sin cambio, stop redefinido a swing H1 del lado barrido (`strategy/liquidity_sweep_ifvg_v4.py`, `backtest/run_v4.py`, experimento `2026-07-02_strat_liq_sweep_amd_v4`). **Gate (ADR-009): 185 operaciones → "evidencia preliminar, no concluyente".** **La hipótesis de costo se confirmó pero no bastó:** el stop H1 amplió el riesgo medio de 4.5→19.4 pips (4.3×) y bajó el `cost_r` de 0.87R→0.29R (≈3× menos costo, justo lo predicho por el diagnóstico de V3). PERO el edge BRUTO se dio vuelta de +0.12R (V3) a −0.05R (V4): con el stop más amplio y el target aún en el swing M5 (cercano), el reward:risk empeora (avg_win 0.78R→0.39R) aunque el win rate sube (39%→49%). **Neto V4 = −0.35R:** mejor que V3 (−0.76R), aún negativo y peor que V1 (−0.27R). **Conclusión:** ampliar el stop es un trade-off (menos costo a cambio de peor R geométrico), no un arreglo; para rentabilizar habría que mover también el target o bajar el costo por otra vía. Sin Deflated Sharpe (hipótesis única); optimizar activa 6.2.

- **Fase 4 — hipótesis V5 (ADR-011, confluencia multi-timeframe + salida jerárquica):** reemplaza el bias de régimen D1 (ADR-007) por confluencia de 4 fuentes de bias por ESTRUCTURA de swings (D1, H4, sesión NY AM 12:00-15:00 UTC, sesión NY PM 19:00-22:00 UTC — horarios fijos CDMX/UTC-6, no ligados a DST de NY). Regla de confluencia: 3+ fuentes alineadas → operar (confianza 'alta'); 2 alineadas + 2 neutrales (ninguna opuesta) → operar con cautela (confianza 'baja', se registra por operación, no excluye); cualquier otro caso → no operar. POI acotado a equal highs/lows "recientes" (formados desde 22:00 UTC del día anterior, 2h antes de Tokio) — más angosto que el conjunto ampliado de V2. Sweep + confirmación IFVG en M5 igual que V3. **Salida jerárquica** (`features/liquidity_target.py`), evaluada en orden, se detiene en la primera que aplica: (1) FVG en H1 sin rellenar en dirección del movimiento (target = borde lejano, relleno completo); (2) si el día viene oscilando (`regime_vol='baja'` en la barra de entrada), extremo del día calendario UTC hasta la entrada (`day_hi`/`day_lo`, PIT); (3) fallback = swing opuesto M5 (igual V1-V4). **Stop: heredado de V4 (swing H1)** — supuesto explícito no especificado por el usuario para V5, documentado en `strategy/liquidity_sweep_ifvg_v5.py`, sujeto a confirmación/ajuste. Módulos nuevos: `features/bias.py` (bias por estructura, resample H4, bias por sesión aislado por día, point-in-time vía merge_asof), `features/liquidity_target.py`, adiciones a `features/levels.py` (`add_day_extremes`, `add_recent_equal_flag`). `strategy/liquidity_sweep_ifvg_v5.py` y `backtest/run_v5.py` siguen el mismo patrón que V3/V4 (intactos, comparables, guarda `experiments/<fecha>_strat_liq_sweep_confluence_v5/` sin tocarlos). **Nota de proceso:** implementado y verificado con datos sintéticos (unit + integración) fuera del entorno de ejecución habitual del proyecto, por falta de acceso de red para instalar las dependencias completas (`ta`, `pyarrow`, etc.) en esa sesión — pendiente correr `pytest` y el backtest completo de 5 años en el entorno real del usuario antes de leer el resultado como válido. Sin Deflated Sharpe (hipótesis única, ADR-011); optimizar parámetros tras ver resultados activa 6.2.

  **Resultado real V5 (5 años, verificado en el entorno del usuario, 91/91 tests en verde):** 191 operaciones → gate "evidencia preliminar, no concluyente". Neto ALL = **−0.31R** (r_total −59.8R), en la misma liga que V2 (−0.31R) y V4 (−0.35R); mejor que V3 (−0.76R), peor que V1 (−0.27R). Win rate **50.3%**, el más alto de las cinco versiones, pero con `avg_win=0.50` / `avg_loss=-1.14` (asimetría insuficiente para ese win rate). Solo la cohorte 2020 es casi neutral (+0.01R); 2021-2025 todas negativas — **importante:** el humo de 3 meses (`--months 3`) dio +0.40R porque cayó justo en la ventana de 2020, la única benigna; no representativo, lección reforzada sobre no leer ventanas cortas. Diagnóstico por sub-grupo (post-hoc, informativo, NO usado para diseñar V6 directamente por riesgo de sub-agrupación excesiva): confianza `alta` (76 ops, −0.41R) rinde PEOR que `baja` (115 ops, −0.25R) — el concepto de confluencia de 3+ fuentes no se confirmó como mejor señal en esta implementación. Por fuente de target: `day_range` (30 ops, −0.097R) es la menos mala, `fvg_h1` (76 ops, −0.39R) y `swing_opposite` (85 ops, −0.32R) peores — pero n=30 está por debajo del gate mínimo, no se lee como hallazgo, solo como pista.

- **Fase 4 — gestión de breakeven móvil (ADR-012), diagnóstico transversal a V1-V5:** en las cinco hipótesis, `avg_loss` ronda −1.0R a −1.2R sin excepción — ninguna versión "rescata" una operación que se movió a favor y luego se revirtió, porque todas usan una salida binaria (stop completo o target completo, sin punto intermedio). Esto es distinto de cómo el usuario ejecuta el plan en vivo (mueve el stop a breakeven al tocar el primer nivel cercano a favor, ~0.3-0.5R; sin salidas parciales — regla real confirmada por el usuario, no una convención genérica de la industria). Hipótesis: la brecha entre "el plan es rentable operado a mano" y "el backtest da negativo" puede estar en la GESTIÓN, no en la señal de entrada — especialmente relevante dado que V3 ya mostró edge BRUTO positivo (+0.12R) antes de costos. `strategy/trade_management.py` implementa `apply_breakeven_management()`: capa de POST-PROCESAMIENTO aplicada sobre operaciones YA generadas por cualquier versión — no cambia entrada/stop-inicial/target, solo re-simula la salida con el stop movido a `entry_price` (+colchón de costo opcional) la primera vez que el precio se mueve a favor ≥0.4R (punto medio de 0.3-0.5R, aproximación explícita — no detección estructural del swing real, documentada como tal). Aproximación intrabarra: igual convención que `_simulate_exit` original (stop se evalúa antes que target dentro de la misma barra); caso límite verificado y documentado (no oculto) cuando el low de una barra toca exactamente el breakeven recién activado. `backtest/run_v3_be.py` y `backtest/run_v5_be.py` aplican esta capa sobre V3 y V5 respectivamente, reusando sus `_prepare`/`_prepare_m5` intactos, guardan experimentos separados (`..._v3_breakeven`, `..._confluence_v5_breakeven`) sin tocar las versiones base. Reportan además cuántas operaciones se "rescataron" del stop completo (outcome='breakeven' vs 'stop'). **Nota de proceso:** igual que V5, implementado y verificado con datos sintéticos (incluyendo un caso límite real encontrado durante la verificación) fuera del entorno de ejecución del usuario — pendiente correr `pytest` y el backtest de 5 años en el entorno real antes de leer el resultado como válido. Sin Deflated Sharpe (una hipótesis de gestión predefinida); ajustar `breakeven_trigger_r` tras ver resultados activa 6.2.

  **Resultado real ADR-012 (verificado en el entorno del usuario, 5 años):** el breakeven simple **EMPEORÓ ambas versiones, no las mejoró.** V3+BE: win rate se desplomó de 39.2%→15.9%, expectancy de −0.76R→−0.97R (peor). V5+BE: win rate 50.3%→35.1%, expectancy −0.31R→−0.38R (peor). `avg_loss` sí mejoró como se esperaba (V3: −1.74→−1.25; V5: −1.14→−0.74), pero el efecto neto fue negativo porque el breakeven al precio EXACTO de entrada, sin colchón, corta operaciones que iban camino al target justo cuando hacen un retroceso normal hacia la entrada antes de continuar — las convierte en 0R en vez de dejarlas correr al target. **Hallazgo real y explicado, no un bug:** un breakeven sin colchón es más agresivo de lo que parece; "rescatar perdedoras" cuesta más "ganadoras convertidas en empate" de lo que ahorra. Se conserva como conocimiento (sección 12), no se descarta ni se repite.

- **Fase 4 — trailing stop por ESTRUCTURA (ADR-013), corrige ADR-012 con la regla real del usuario:** tras el resultado negativo de ADR-012, se confirmó con el usuario que su regla real NO es breakeven a precio de entrada — es un **trailing stop por estructura**: el stop avanza al swing confirmado que queda "un impulso atrás" del más reciente (nunca al más nuevo, deja colchón de un impulso completo), solo a favor (nunca se afloja). Ejemplo dado por el usuario: con 2 impulsos formados, usa el primero; al confirmarse un 3º, avanza al segundo. Para un short usa swing HIGHS confirmados (el stop debe quedar arriba); para un long, swing LOWS — reutiliza exactamente la misma detección de estructura de ADR-004 (`features/structure.py`, misma confirmación con lag point-in-time), sin features nuevas: todo el trabajo nuevo está en `strategy/trade_management.py` (`apply_structure_trailing_stop`, `_simulate_exit_trailing_structure`), verificado con 5 casos sintéticos (incluye el ejemplo exacto del usuario, no-aflojar el stop, y no-salida-prematura al tocar un swing no activo). `backtest/run_v3_trail.py` y `backtest/run_v5_trail.py` siguen el mismo patrón de post-procesamiento sobre operaciones ya generadas (entrada/stop-inicial/target intactos), guardan experimentos separados (`..._v3_trailing`, `..._confluence_v5_trailing`) sin tocar V3/V5/ADR-012. **Nota de proceso:** verificado con datos sintéticos fuera del entorno de ejecución del usuario (misma limitación de red de siempre) — pendiente correr `pytest` y el backtest de 5 años reales. Sin Deflated Sharpe (hipótesis predefinida); ajustar `lag_swings` tras ver resultados activa 6.2.

  **Resultado real ADR-013 (verificado en el entorno del usuario, 5 años):** el trailing por estructura mejora la dirección correcta (a diferencia del breakeven simple, que empeoraba). **V3+Trailing:** casi sin efecto (win rate 39.2%→38.4%, expectancy −0.76R→−0.76R, solo 12/245 salidas vía trailing) — el stop de V3 (mecha M5) ya es tan ajustado que el trailing rara vez tiene espacio para actuar antes de tocarlo. **V5+Trailing:** mejora real (win rate 50.3%→39.8%, pero expectancy −0.31R→−0.24R, `avg_loss` −1.14→−0.74, 71/191 salidas vía trailing) — el stop de V5 (swing H1, más ancho) sí da espacio al trailing para cortar pérdidas más chicas antes del stop original. **Conclusión:** el trailing ayuda cuando el stop de partida es ancho, no cuando ya es ajustado — motiva ADR-014 (probar la señal más simple, V1, con el stop ancho, para maximizar el espacio de acción del trailing).

- **Fase 4 — ADR-014: señal de V1 + stop de swing H1 + trailing (V6):** de las 9 variantes probadas hasta ahora (V1-V5, +breakeven en V3/V5, +trailing en V3/V5), V1 —la más simple, sin confluencia ni AMD— tuvo la mejor expectativa (−0.27R). Su stop original es la mecha de la propia vela H1 del sweep (ya más ancho que el de V3 en M5, pero no es el swing estructural real). V6 (`strategy/liquidity_sweep_ifvg_v6.py`) reutiliza `daily_bias_from_d1`, `_sweep_at` y `_simulate_exit` de V1 sin cambios — el ÚNICO cambio es el stop: pasa de "mecha de la vela del sweep" a "swing H1 confirmado" (mismo criterio de ADR-010 aplicado sobre V3→V4, ahora sobre V1). `backtest/run_v6.py` (base) y `backtest/run_v6_trail.py` (+ trailing de ADR-013) siguen el mismo patrón de las demás versiones — intactas, comparables, experimentos separados (`..._ifvg_v6`, `..._ifvg_v6_trailing`) sin tocar V1-V5. Verificado con 2 casos sintéticos (confirma que el stop usa el swing H1 y no la mecha; confirma que sin swing H1 válido no se opera). **Nota de proceso:** igual que las versiones anteriores, verificado con datos sintéticos fuera del entorno de ejecución del usuario — pendiente correr `pytest` y ambos backtests de 5 años reales antes de leer el resultado como válido.

- **Fase 5** — Refinamiento de reportes y comparación entre cohortes.
- **Fase 6+** — Evaluar expansión a otro activo/timeframe, y evaluar HMM/clustering como alternativa al baseline de régimen, solo si hay evidencia de que el baseline es insuficiente.

---

## 15. No-Objetivos

Este proyecto no es: un bot de alta frecuencia, una plataforma de copy-trading, un generador de señales para vender, un bróker, ni un reemplazo de plataformas de charting.

---

## 16. Claude — reglas de trabajo en este proyecto

- No implementar nada de una fase futura mientras la fase actual esté incompleta.
- No agregar activos, timeframes o mercados nuevos sin que el usuario lo pida explícitamente.
- No usar ninguna fuente de datos, librería o servicio que no esté explícitamente aprobado en la sección 4. Cualquier fuente nueva requiere un ADR.
- Todo hallazgo estadístico debe indicar la cohorte temporal en la que se basa.
- Los parámetros de ADR-003/004 (umbrales de ADX, percentiles de ATR, `k` del fractal, ventana de sweep) son defaults documentados, no constantes sagradas — pero cualquier cambio se trata como un experimento nuevo con su propio control de tests múltiples, no como un ajuste silencioso.
- Toda serie cross-asset se integra respetando point-in-time (merge-asof sobre fecha de efectividad real), sin excepción.
- Ante cualquier ambigüedad, Claude Code se detiene y pregunta — no asume, no inventa APIs, no inventa datasets.
- Priorizar siempre: que el sistema funcione de punta a punta para AUD/USD, por encima de que esté "completo" en teoría.
