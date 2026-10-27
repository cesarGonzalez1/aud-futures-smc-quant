"""Test de segmentación en cohortes (sección 6.4)."""

from __future__ import annotations

import pandas as pd
import pytest

from analysis.cohorts import add_cohort


def test_calendar_year_cohort():
    idx = pd.to_datetime(["2021-06-01", "2022-01-15", "2023-12-31"]).tz_localize("UTC")
    df = pd.DataFrame({"x": [1, 2, 3]}, index=idx)
    df.index.name = "timestamp"
    out = add_cohort(df)
    assert out["cohort"].tolist() == ["2021", "2022", "2023"]


def test_unsupported_mode_raises():
    df = pd.DataFrame({"x": [1]}, index=pd.to_datetime(["2021-01-01"]).tz_localize("UTC"))
    with pytest.raises(ValueError):
        add_cohort(df, mode="weekly")
