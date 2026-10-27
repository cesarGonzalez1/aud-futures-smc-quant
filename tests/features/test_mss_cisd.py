import pandas as pd
import pytest

from features.mss_cisd import add_mss_flags, find_cisd


def test_add_mss_flags_requires_structure_columns():
    df = pd.DataFrame({"close": [1.0, 2.0]})
    with pytest.raises(ValueError):
        add_mss_flags(df)


def test_add_mss_flags_bull_and_bear():
    df = pd.DataFrame({
        "close": [1.05, 0.95, 1.00],
        "last_swing_high": [1.02, 1.02, 1.02],
        "last_swing_low": [0.98, 0.98, 0.98],
    })
    out = add_mss_flags(df)
    assert out.loc[0, "mss_bull"] and not out.loc[0, "mss_bear"]
    assert out.loc[1, "mss_bear"] and not out.loc[1, "mss_bull"]
    assert not out.loc[2, "mss_bull"] and not out.loc[2, "mss_bear"]


def test_find_cisd_bull_direction():
    idx = pd.date_range("2024-01-01", periods=4, freq="5min")
    window = pd.DataFrame({"close": [0.99, 1.00, 1.03, 1.05]}, index=idx)
    hit = find_cisd(window, reference_open=1.02, direction="bull")
    assert hit == idx[2]


def test_find_cisd_none_when_no_break():
    idx = pd.date_range("2024-01-01", periods=3, freq="5min")
    window = pd.DataFrame({"close": [1.00, 1.01, 1.015]}, index=idx)
    hit = find_cisd(window, reference_open=1.02, direction="bull")
    assert hit is None


def test_find_cisd_invalid_direction():
    idx = pd.date_range("2024-01-01", periods=2, freq="5min")
    window = pd.DataFrame({"close": [1.0, 1.1]}, index=idx)
    with pytest.raises(ValueError):
        find_cisd(window, reference_open=1.0, direction="sideways")
