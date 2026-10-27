"""Segmentación temporal en cohortes (sección 6.4).

Los 5 años no se tratan como bloque homogéneo: cada análisis se reporta por
cohorte para exponer si una relación es estable o específica de un período. La
partición mínima es el año calendario.
"""

from __future__ import annotations

import pandas as pd

COHORT_COL = "cohort"


def add_cohort(df: pd.DataFrame, *, mode: str = "calendar_year") -> pd.DataFrame:
    """Añade la columna `cohort` según el modo indicado.

    Args:
        df: DataFrame con índice temporal.
        mode: "calendar_year" (único soportado por ahora). Otro valor => error
            explícito (regla sección 16), no un default silencioso.

    Returns:
        Copia de `df` con la columna `cohort` (str).
    """
    if mode != "calendar_year":
        raise ValueError(f"Modo de cohorte no soportado: {mode!r}")
    out = df.copy()
    out[COHORT_COL] = out.index.year.astype(str)
    return out
