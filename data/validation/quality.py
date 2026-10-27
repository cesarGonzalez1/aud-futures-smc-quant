"""Validación de calidad de datos (ADR-001, sección 13).

Un dataset NO se considera "raw validado" hasta pasar estos chequeos. Cada chequeo
es una función pura que devuelve una lista de problemas (vacía si todo bien). La
suite pytest (tests/data/test_quality.py) las ejecuta como tests; un dataset con
problemas críticos detiene el pipeline de ingesta.

Chequeos:
  - Esquema: columnas OHLC presentes, dtypes numéricos.
  - Índice: tz-aware UTC, ordenado, sin duplicados.
  - Coherencia OHLC: high>=low, high>=max(open,close), low<=min(open,close).
  - Nulos en OHLC.
  - Huecos temporales vs. frecuencia esperada (tolerando cierre de fin de semana).
  - Outliers de precio por retorno log (|z| > umbral configurable).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from data import schema


@dataclass
class QualityReport:
    """Resultado de validar un dataset.

    Attributes:
        errors: problemas críticos; el dato NO es válido si la lista no está vacía.
        warnings: problemas tolerables (ej. huecos de fin de semana esperados).
    """

    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        """True si no hay errores críticos."""
        return not self.errors

    def extend(self, other: "QualityReport") -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)


def check_schema(df: pd.DataFrame) -> QualityReport:
    """Verifica columnas OHLC requeridas y que sean numéricas."""
    report = QualityReport()
    for col in schema.REQUIRED_COLUMNS:
        if col not in df.columns:
            report.errors.append(f"Falta columna requerida: {col!r}")
        elif not pd.api.types.is_numeric_dtype(df[col]):
            report.errors.append(f"Columna {col!r} no es numérica")
    return report


def check_index(df: pd.DataFrame) -> QualityReport:
    """Verifica índice temporal: nombre, tz UTC, orden, sin duplicados."""
    report = QualityReport()
    idx = df.index
    if idx.name != schema.TIMESTAMP:
        report.errors.append(
            f"Índice debe llamarse {schema.TIMESTAMP!r}, es {idx.name!r}"
        )
    if not isinstance(idx, pd.DatetimeIndex):
        report.errors.append("Índice debe ser DatetimeIndex")
        return report  # sin DatetimeIndex, los demás chequeos no aplican
    if idx.tz is None or str(idx.tz) != "UTC":
        report.errors.append("Índice debe ser tz-aware en UTC (sección 11)")
    if not idx.is_monotonic_increasing:
        report.errors.append("Índice no está ordenado ascendente")
    dups = int(idx.duplicated().sum())
    if dups:
        report.errors.append(f"Índice tiene {dups} timestamps duplicados")
    return report


def check_ohlc_coherence(df: pd.DataFrame) -> QualityReport:
    """Verifica invariantes de barra: high es máximo, low es mínimo, sin nulos."""
    report = QualityReport()
    o, h, l, c = schema.OPEN, schema.HIGH, schema.LOW, schema.CLOSE
    if any(col not in df.columns for col in (o, h, l, c)):
        return report  # check_schema ya reportó la ausencia

    nulls = int(df[[o, h, l, c]].isna().any(axis=1).sum())
    if nulls:
        report.errors.append(f"{nulls} filas con nulos en OHLC")

    bad_hl = int((df[h] < df[l]).sum())
    if bad_hl:
        report.errors.append(f"{bad_hl} barras con high < low")

    bad_h = int(((df[h] < df[o]) | (df[h] < df[c])).sum())
    if bad_h:
        report.errors.append(f"{bad_h} barras con high < open/close")

    bad_l = int(((df[l] > df[o]) | (df[l] > df[c])).sum())
    if bad_l:
        report.errors.append(f"{bad_l} barras con low > open/close")
    return report


def _calendar_trading_days_between(market_calendar: str, prev, ts):
    """Días de trading del calendario estrictamente entre `prev` y `ts` (exclusivo).

    Si está vacío, el hueco se explica solo por fines de semana/feriados del
    calendario (cierre esperado). Import perezoso para no cargar la librería salvo
    que se use un calendario de mercado.
    """
    import pandas_market_calendars as mcal

    cal = mcal.get_calendar(market_calendar)
    lo = (prev.normalize() + pd.Timedelta(days=1)).tz_localize(None)
    hi = (ts.normalize() - pd.Timedelta(days=1)).tz_localize(None)
    if lo > hi:
        return []
    return list(cal.valid_days(start_date=lo, end_date=hi))


def check_gaps(
    df: pd.DataFrame,
    timeframe: str,
    *,
    weekend_gap_allowed: bool = True,
    error_gap_days: float = 7.0,
    weekend_max_days: float = 4.0,
    market_calendar: str | None = None,
) -> QualityReport:
    """Detecta huecos temporales vs. la frecuencia esperada del timeframe.

    Filosofía de severidad: un hueco NO corrompe las barras que sí están presentes
    — es un problema de *completitud*, no de *validez*. Los datos reales de forex y
    metales están llenos de huecos legítimos (cierre de fin de semana, pausa diaria
    de mantenimiento del oro, feriados de mercado). Por eso los huecos se reportan
    como **warning** por defecto, para que sean visibles (en el reporte y contra el
    `row_count` del manifest) sin descartar datos buenos.

    El criterio de severidad es en **días naturales**, NO en barras, para que sea
    independiente del timeframe (un fin de semana forex son ~2 días = 48 barras en
    H1 pero ~576 barras en M5; contar barras daría un umbral distinto por timeframe).

    Orden de clasificación de cada hueco:
      1. Fin de semana (empieza viernes) y ≤ `weekend_max_days` → warning esperado.
         Se evalúa PRIMERO y sin importar el número de barras.
      2. Con `market_calendar`: hueco explicado por feriados/cierres → warning
         esperado; con días de trading faltantes → warning no explicado.
      3. > `error_gap_days` (y no cubierto arriba) → error (pérdida gruesa real).
      4. Resto → warning.

    Args:
        df: dataset con índice temporal ordenado.
        timeframe: para derivar la frecuencia esperada (schema.freq_for).
        weekend_gap_allowed: etiquetar el hueco de fin de semana como esperado.
        error_gap_days: días naturales por encima de los cuales un hueco no
            explicado se considera error (default 7).
        weekend_max_days: duración máxima de un hueco que empieza viernes para
            considerarse cierre de fin de semana (default 4, cubre finde + feriado).
        market_calendar: calendario de `pandas_market_calendars` (ej. "CME_FX" para
            6A, ADR-006) para clasificar huecos por feriado de mercado.
    """
    report = QualityReport()
    if len(df) < 2:
        return report
    freq = pd.Timedelta(schema.freq_for(timeframe))
    deltas = df.index.to_series().diff().dropna()
    gaps = deltas[deltas > freq]

    for ts, gap in gaps.items():
        prev = ts - gap
        missing_bars = int(round(gap / freq)) - 1
        gap_days = gap.total_seconds() / 86400.0
        msg = f"Hueco de {gap} ({missing_bars} barras) antes de {ts.isoformat()}"

        # 1. Fin de semana: se evalúa primero, sin importar el nº de barras.
        if weekend_gap_allowed and prev.weekday() == 4 and gap_days <= weekend_max_days:
            report.warnings.append(msg + " (fin de semana, esperado)")
            continue

        # 2. Calendario de mercado (ej. CME para 6A).
        if market_calendar is not None:
            missing_days = _calendar_trading_days_between(market_calendar, prev, ts)
            if not missing_days:
                report.warnings.append(msg + f" (cierre/feriado {market_calendar}, esperado)")
            else:
                report.warnings.append(
                    msg + f" ({len(missing_days)} días de trading {market_calendar} faltantes)"
                )
            continue

        # 3. Pérdida gruesa real.
        if gap_days > error_gap_days:
            report.errors.append(msg + " (pérdida gruesa de datos)")
            continue

        # 4. Resto: hueco tolerable (feriado corto, microestructura).
        report.warnings.append(msg)
    return report


def check_price_outliers(df: pd.DataFrame, zscore_threshold: float) -> QualityReport:
    """Marca retornos log con |z-score robusto| > umbral como outliers a revisar.

    Usa z-score robusto (mediana + MAD) en vez de media/desviación estándar: un
    outlier real no infla la mediana ni la MAD, así que no se enmascara a sí mismo
    (problema clásico del z clásico en muestras chicas o con pocos saltos grandes).

    Se reporta como warning (no error): un salto grande puede ser real (evento de
    mercado) o un error de datos. La decisión de descartar es humana / de un
    experimento, no automática — el sistema solo señala.
    """
    report = QualityReport()
    close = df.get(schema.CLOSE)
    if close is None or len(close) < 3:
        return report
    log_ret = np.log(close / close.shift(1)).dropna()
    median = log_ret.median()
    mad = (log_ret - median).abs().median()
    if mad == 0 or np.isnan(mad):
        return report
    # 1.4826 hace la MAD comparable a la desviación estándar bajo normalidad.
    robust_z = (log_ret - median) / (1.4826 * mad)
    outliers = robust_z[robust_z.abs() > zscore_threshold]
    for ts, zval in outliers.items():
        report.warnings.append(
            f"Outlier de precio en {ts.isoformat()} (z_robusto={zval:.1f})"
        )
    return report


def validate(
    df: pd.DataFrame,
    timeframe: str,
    *,
    zscore_threshold: float = 8.0,
    weekend_gap_allowed: bool = True,
    error_gap_days: float = 7.0,
    market_calendar: str | None = None,
) -> QualityReport:
    """Corre todos los chequeos y agrega el reporte combinado.

    Args:
        df: dataset en esquema canónico.
        timeframe: timeframe del dataset.
        zscore_threshold: umbral de outlier de retorno log (config quality).
        weekend_gap_allowed: tolerar hueco de fin de semana forex.
        error_gap_days: días naturales por encima de los cuales un hueco no
            explicado es error (independiente del timeframe).
        market_calendar: calendario de mercado para clasificar huecos (ej. CME_FX).

    Returns:
        QualityReport combinado. `is_valid` False => no ingresar el dato.
    """
    report = QualityReport()
    report.extend(check_schema(df))
    report.extend(check_index(df))
    # Si esquema/índice fallan, los chequeos de contenido pueden dar ruido:
    if not report.is_valid:
        return report
    report.extend(check_ohlc_coherence(df))
    report.extend(
        check_gaps(
            df, timeframe,
            weekend_gap_allowed=weekend_gap_allowed,
            error_gap_days=error_gap_days,
            market_calendar=market_calendar,
        )
    )
    report.extend(check_price_outliers(df, zscore_threshold))
    return report
