"""Esquema canónico de datos OHLCV del proyecto.

Todo el sistema habla un único formato de barra. Los adaptadores de fuente
(Dukascopy, Stooq) tienen la responsabilidad de normalizar su salida a este
esquema ANTES de que el dato se considere ingresable. Cualquier módulo aguas
abajo (features, analysis) puede asumir estas columnas, estos dtypes y estas
invariantes sin volver a validarlas.

Invariantes garantizadas tras la validación de calidad (ADR-001, sección 13):
  - Índice = timestamp en UTC (tz-aware), ordenado ascendente, sin duplicados.
  - high >= low, high >= open, high >= close, low <= open, low <= close.
  - Sin valores nulos en columnas OHLC.
"""

from __future__ import annotations

# Nombre del índice temporal. Siempre UTC, tz-aware (sección 11).
TIMESTAMP = "timestamp"

# Columnas OHLCV canónicas.
OPEN = "open"
HIGH = "high"
LOW = "low"
CLOSE = "close"
VOLUME = "volume"

# Spread bid/ask cuando la fuente lo provee (Dukascopy sí; requerido para
# modelar costos de transacción en Fase 4, sección 6.3).
SPREAD = "spread"

OHLC_COLUMNS: tuple[str, ...] = (OPEN, HIGH, LOW, CLOSE)
OHLCV_COLUMNS: tuple[str, ...] = (OPEN, HIGH, LOW, CLOSE, VOLUME)

# --- Roles de instrumento (ADR-006) ---
# real    = el activo realmente operado (6A, futuro CME del AUD).
# proxy   = sustituto documentado que aproxima al real (AUDUSD spot para estructura
#           intradía, porque 6A no se descarga intradía). Nunca se presenta como el real.
# context = cross-asset de apoyo (XAU, DXY, tasas).
ROLE_REAL = "real"
ROLE_PROXY = "proxy"
ROLE_CONTEXT = "context"
VALID_ROLES: tuple[str, ...] = (ROLE_REAL, ROLE_PROXY, ROLE_CONTEXT)


def validate_role(role: str) -> str:
    """Valida un rol de instrumento; error explícito si es desconocido (sección 16)."""
    if role not in VALID_ROLES:
        raise ValueError(f"Rol de instrumento inválido: {role!r}. Válidos: {VALID_ROLES}")
    return role

# Columnas mínimas que un adaptador DEBE entregar. VOLUME y SPREAD son opcionales
# porque no todas las fuentes gratuitas los proveen (ej. Stooq diario para DXY).
REQUIRED_COLUMNS: tuple[str, ...] = OHLC_COLUMNS

# Frecuencia esperada por timeframe, en notación pandas offset alias.
# Se usa para detectar huecos (validación de calidad) y para merge_asof.
TIMEFRAME_FREQ: dict[str, str] = {
    "M1": "1min",
    "M5": "5min",
    "H1": "1h",
    "H4": "4h",
    "D1": "1D",
}


def freq_for(timeframe: str) -> str:
    """Devuelve el offset alias de pandas para un timeframe soportado.

    Args:
        timeframe: uno de las claves de TIMEFRAME_FREQ (ej. "H1").

    Returns:
        Offset alias de pandas (ej. "1h").

    Raises:
        KeyError: si el timeframe no está soportado. No se asume un default:
            un timeframe desconocido es un error explícito (regla sección 16).
    """
    if timeframe not in TIMEFRAME_FREQ:
        raise KeyError(
            f"Timeframe no soportado: {timeframe!r}. "
            f"Soportados: {sorted(TIMEFRAME_FREQ)}"
        )
    return TIMEFRAME_FREQ[timeframe]
