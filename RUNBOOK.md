# Runbook Operativo

Este proyecto se ejecuta por capas. La secuencia correcta es:

1. preparar entorno
2. ingerir datos crudos
3. construir features
4. correr análisis estadístico
5. generar reporte de mercado
6. correr backtests exploratorios

## 1. Preparar entorno

Comando recomendado:

```bash
make install
```

Si `make install` falla porque no existe `python3.11`, usa el intérprete disponible en tu máquina para crear la venv e instalar dependencias. El objetivo es terminar con un entorno que sí tenga `pandas`, `pyarrow`, `scipy`, `statsmodels`, `ta` y `dukascopy-python`.

Chequeo mínimo después de instalar:

```bash
. .venv/bin/activate
python -c "import pandas; print(pandas.__version__)"
```

## 2. Ingesta de datos

Comando:

```bash
make ingest
```

Qué hace:
- descarga AUDUSD, XAUUSD, DXY y 6A según `config/settings.yaml`
- valida calidad de cada dataset
- escribe `data/raw/<symbol>/<timeframe>/data.parquet`
- escribe `manifest.json` con `sha256`

Qué debe salir:
- un resumen por símbolo/timeframe con `✓` o `✗`
- conteo de filas
- mensaje `OK [proxy]`, `OK [context]` o `OK [real]` cuando todo está bien

## 3. Features

Comando:

```bash
make features
```

Qué hace:
- lee `data/raw/AUDUSD/H1`
- calcula indicadores, sesiones, estructura, volatilidad realizada y target futuro
- une contexto cross-asset
- escribe `data/features/AUDUSD/H1/data.parquet` con `parent_sha256`

Qué debe salir:
- filas del dataset derivado
- `role=proxy`
- hash del dataset y hash padre

## 4. Análisis de régimen

Comando recomendado:

```bash
make analyze-garch-wf
```

Qué hace:
- añade cohortes por año
- detecta régimen por reglas
- compara régimen contra baseline GARCH walk-forward
- guarda experimento en `experiments/<fecha>_regime_vs_garch_walkforward/`

Qué debe salir:
- tablas por cohorte
- `p_fdr`
- `epsilon2`
- veredicto tipo `aporta sobre GARCH-wf`

## 5. Reporte de mercado

Comando:

```bash
make report
```

Qué hace:
- lee features de AUDUSD H1
- resume estado actual: régimen, sesiones, ADX, ATR, RSI, sweeps
- toma como evidencia principal el experimento walk-forward más reciente
- escribe `reports/<fecha>_market_state.md`

Qué debe salir:
- un Markdown con 6 secciones
- advertencia visible de proxy spot AUD/USD
- lectura del régimen actual y estructura reciente

## 6. Backtests exploratorios

Orden recomendado:

```bash
make backtest
make backtest-v2
make backtest-v3
make backtest-v4
```

Qué hace cada uno:
- `backtest`: V1, sweep + IFVG
- `backtest-v2`: V2, AMD con acumulación y POIs ampliados
- `backtest-v3`: V3, mecánica completa en M5
- `backtest-v4`: V4, V3 con stop en swing H1

Qué debe salir:
- número de operaciones
- métricas netas por cohorte
- archivo de experimento en `experiments/<fecha>_strat_.../`

## 7. Lectura de resultados

Interpretación actual del sistema:

- El régimen sí aporta valor predictivo sobre volatilidad futura, incluso contra GARCH walk-forward.
- El efecto es pequeño; no es una señal operable por sí solo.
- Las estrategias V1-V4 siguen siendo netamente negativas después de costos.
- V3 mostró edge bruto positivo, pero los costos lo destruyen.
- V4 baja el costo relativo, pero empeora el reward:risk.

## 8. Errores típicos

### `zsh: command not found: python`

No es un error del proyecto. Ese shell no tiene `python` como alias. Usa `python3` o activa la venv y ejecuta `python` dentro de ella.

### `ModuleNotFoundError: No module named 'pandas'`

Significa que estás usando un intérprete sin dependencias instaladas. No basta con que el módulo `data.ingest` exista; el entorno también necesita los paquetes del proyecto.

### `No module named data`

Suele significar que estás ejecutando desde fuera de la raíz del repo o sin usar `python -m data.ingest` desde el directorio del proyecto.

## 9. Resumen corto

Si quieres probar todo el sistema desde cero:

```bash
make install
make ingest
make features
make analyze-garch-wf
make report
make backtest-v4
```

Ese es el recorrido completo más útil para validar el estado actual del proyecto.