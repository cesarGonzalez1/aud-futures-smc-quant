"""Tabla curada de tasas RBA vs. Fed (ADR-005).

Diferencial de política monetaria construido a mano desde fuentes oficiales
(rba.gov.au, federalreserve.gov). Una fila por decisión de política, con la fecha
de ANUNCIO real. Point-in-time-safe por naturaleza: una tasa anunciada no se
revisa retroactivamente (a diferencia de PIB/empleo). Se une a precio con
merge_asof sobre la fecha de anuncio, nunca con fecha futura.

RIESGO HUMANO (reauditoría v2.2): la tabla es manual; una decisión faltante
corrompe el merge en silencio. `validate_completeness` mitiga esto verificando
estructura y continuidad temporal. La correctitud de valores contra la fuente
oficial es un test aparte (tests/data/test_rates_table.py).

Formato del CSV (data/raw/rates/rba_fed.csv):
    fecha_efectiva,tasa_RBA,tasa_Fed,fuente_url
    2020-07-07,0.25,0.125,https://www.rba.gov.au/...
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = (
    "fecha_efectiva",
    "tasa_RBA",
    "tasa_Fed",
    "fuente_url",
)


def load(path: str | Path) -> pd.DataFrame:
    """Carga la tabla curada de tasas y la deja lista para merge_asof.

    Args:
        path: ruta al CSV curado.

    Returns:
        DataFrame ordenado por `fecha_efectiva` (UTC, tz-aware), con columna
        derivada `diferencial` = tasa_RBA - tasa_Fed.

    Raises:
        FileNotFoundError: si el CSV no existe.
        ValueError: si faltan columnas requeridas.
    """
    path = Path(path)
    df = pd.read_csv(path, comment="#", skip_blank_lines=True)
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Tabla de tasas: faltan columnas {missing}")

    df["fecha_efectiva"] = pd.to_datetime(df["fecha_efectiva"], utc=True)
    df = df.sort_values("fecha_efectiva").reset_index(drop=True)
    df["diferencial"] = df["tasa_RBA"] - df["tasa_Fed"]
    return df


def validate_completeness(df: pd.DataFrame, max_gap_days: int = 120) -> list[str]:
    """Verifica estructura y continuidad temporal de la tabla curada.

    No valida que los valores sean correctos contra la fuente (eso es un test
    dedicado); valida que no haya huecos sospechosamente largos entre decisiones
    (los bancos centrales se reúnen ~cada 6 semanas; un hueco > max_gap_days
    sugiere una decisión olvidada).

    Args:
        df: tabla ya cargada por `load`.
        max_gap_days: hueco máximo tolerado entre filas consecutivas.

    Returns:
        Lista de problemas (vacía si la tabla está completa y bien formada).
    """
    problems: list[str] = []
    if df.empty:
        return ["Tabla de tasas vacía"]

    if df["fecha_efectiva"].duplicated().any():
        problems.append("Fechas de decisión duplicadas en tabla de tasas")

    for col in ("tasa_RBA", "tasa_Fed"):
        if df[col].isna().any():
            problems.append(f"Valores nulos en {col}")

    gaps = df["fecha_efectiva"].diff().dropna()
    long_gaps = gaps[gaps > pd.Timedelta(days=max_gap_days)]
    for i, gap in long_gaps.items():
        fecha = df.loc[i, "fecha_efectiva"].date().isoformat()
        problems.append(
            f"Hueco de {gap.days} días antes de {fecha} "
            f"(> {max_gap_days}; posible decisión faltante)"
        )
    return problems


def merge_into(
    price: pd.DataFrame,
    rates: pd.DataFrame,
    columns: tuple[str, ...] = ("tasa_RBA", "tasa_Fed", "diferencial"),
) -> pd.DataFrame:
    """Une el diferencial de tasas a una serie de precio de forma point-in-time.

    Usa merge_asof (backward): a cada barra en `t` se le asigna la última decisión
    de tasa con `fecha_efectiva <= t`. Nunca usa una decisión futura.

    Args:
        price: DataFrame de precio con índice temporal UTC ordenado.
        rates: tabla de tasas cargada por `load`.
        columns: columnas de tasas a incorporar.

    Returns:
        Copia de `price` con las columnas de tasas añadidas.
    """
    left = price.sort_index()
    merged = pd.merge_asof(
        left.reset_index(),
        rates[["fecha_efectiva", *columns]],
        left_on=left.index.name,
        right_on="fecha_efectiva",
        direction="backward",
    )
    merged = merged.set_index(left.index.name)
    return merged.drop(columns=["fecha_efectiva"])
