"""Tests de la tabla curada de tasas (ADR-005, sección 13).

Mitiga el riesgo humano de la tabla manual: estructura, completitud, y que el
merge point-in-time nunca use una decisión futura.
"""

from __future__ import annotations

import pandas as pd

from data.sources import rates_table as rt


def _write_csv(path, rows: str) -> str:
    header = "fecha_efectiva,tasa_RBA,tasa_Fed,fuente_url\n"
    path.write_text(header + rows, encoding="utf-8")
    return str(path)


def test_load_computes_differential(tmp_path):
    csv = _write_csv(
        tmp_path / "r.csv",
        "2021-01-01,0.10,0.125,url\n2022-06-01,0.85,1.625,url\n",
    )
    df = rt.load(csv)
    assert list(df["diferencial"]) == [0.10 - 0.125, 0.85 - 1.625]
    assert str(df["fecha_efectiva"].dt.tz) == "UTC"


def test_completeness_flags_long_gap(tmp_path):
    csv = _write_csv(
        tmp_path / "r.csv",
        "2021-01-01,0.10,0.125,url\n2023-01-01,0.10,0.125,url\n",  # ~2 años
    )
    problems = rt.validate_completeness(rt.load(csv), max_gap_days=120)
    assert any("Hueco" in p for p in problems)


def test_merge_asof_is_point_in_time(tmp_path):
    csv = _write_csv(
        tmp_path / "r.csv",
        "2021-01-01,0.10,0.125,url\n2021-01-10,0.50,0.125,url\n",
    )
    rates = rt.load(csv)
    idx = pd.date_range("2021-01-05", "2021-01-12", freq="1D", tz="UTC")
    price = pd.DataFrame({"close": range(len(idx))}, index=idx)
    price.index.name = "timestamp"
    merged = rt.merge_into(price, rates)
    # Antes del 10-ene aplica 0.10; desde el 10-ene aplica 0.50. Nunca futuro.
    assert merged.loc["2021-01-05", "tasa_RBA"] == 0.10
    assert merged.loc["2021-01-11", "tasa_RBA"] == 0.50
