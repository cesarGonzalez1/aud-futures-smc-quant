"""Test de sesiones y DST (sección 11).

Verifica que el mapeo de barra->sesión respeta el horario de verano: la sesión de
Londres (08:00-17:00 local) cae en distinta hora UTC en invierno (GMT) y en
verano (BST = UTC+1), y el módulo debe reflejarlo sin offsets fijos.
"""

from __future__ import annotations

import pandas as pd

from data import schema

from features import sessions

SESSIONS_CFG = {
    "London": {"tz": "Europe/London", "open_local": "08:00", "close_local": "17:00"},
    "NewYork": {"tz": "America/New_York", "open_local": "08:00", "close_local": "17:00"},
}


def _bar_at(utc_str: str) -> pd.DataFrame:
    idx = pd.DatetimeIndex([pd.Timestamp(utc_str, tz="UTC")], name=schema.TIMESTAMP)
    return pd.DataFrame({schema.CLOSE: [1.0]}, index=idx)


def test_london_session_shifts_with_dst():
    # 07:30 UTC:
    #   Invierno (GMT): 07:30 local -> ANTES de 08:00 -> fuera de Londres.
    #   Verano (BST=UTC+1): 08:30 local -> DENTRO de Londres.
    winter = sessions.add_sessions(_bar_at("2024-01-15 07:30"), SESSIONS_CFG)
    summer = sessions.add_sessions(_bar_at("2024-07-15 07:30"), SESSIONS_CFG)
    assert not winter["in_london"].iloc[0]
    assert summer["in_london"].iloc[0]


def test_overlap_london_ny():
    # 14:00 UTC en verano: Londres 15:00 BST (abierto), NY 10:00 EDT (abierto).
    df = sessions.add_sessions(_bar_at("2024-07-15 14:00"), SESSIONS_CFG)
    assert df["in_london"].iloc[0]
    assert df["in_newyork"].iloc[0]
    assert df["overlap_london_ny"].iloc[0]
