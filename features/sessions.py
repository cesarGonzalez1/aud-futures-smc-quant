"""Features de sesión de mercado con manejo correcto de DST (sección 11).

Todo el índice está en UTC. Cada sesión se define por su horario LOCAL de plaza y
su zona horaria (`zoneinfo`), de modo que el cambio de horario de verano (DST) de
cada plaza se resuelve automáticamente y de forma independiente: en invierno
Londres abre 08:00 GMT = 08:00 UTC, en verano 08:00 BST = 07:00 UTC, y este módulo
lo refleja sin offsets fijos.
"""

from __future__ import annotations

from zoneinfo import ZoneInfo

import pandas as pd


def _to_minutes(hhmm: str) -> int:
    h, m = hhmm.split(":")
    return int(h) * 60 + int(m)


def add_sessions(df: pd.DataFrame, sessions_cfg: dict) -> pd.DataFrame:
    """Añade una columna booleana `in_<sesion>` por cada sesión + solapamiento.

    Args:
        df: DataFrame con índice UTC tz-aware.
        sessions_cfg: dict {nombre: {tz, open_local, close_local}} (config sección
            `sessions`). Los horarios se interpretan en la zona de la plaza.

    Returns:
        Copia de `df` con columnas `in_<nombre>` (minúsculas) y, si existen Londres
        y Nueva York, `overlap_london_ny` (foco del usuario, sección 2).
    """
    out = df.copy()
    idx = out.index

    for name, cfg in sessions_cfg.items():
        local = idx.tz_convert(ZoneInfo(cfg["tz"]))
        local_minutes = local.hour * 60 + local.minute
        open_m = _to_minutes(cfg["open_local"])
        close_m = _to_minutes(cfg["close_local"])
        # Sesión dentro del mismo día local (nuestras sesiones no cruzan medianoche).
        out[f"in_{name.lower()}"] = (local_minutes >= open_m) & (local_minutes < close_m)

    if "in_london" in out.columns and "in_newyork" in out.columns:
        out["overlap_london_ny"] = out["in_london"] & out["in_newyork"]
    return out
