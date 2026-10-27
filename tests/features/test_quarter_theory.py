import pandas as pd

from features.quarter_theory import add_quarter_context, nearest_quarter_levels, quarter_target


def test_nearest_quarter_levels_basic():
    lower, upper = nearest_quarter_levels(0.6543, step=0.0025)
    assert lower <= 0.6543 <= upper
    assert round(upper - lower, 10) == 0.0025


def test_nearest_quarter_levels_exact_on_level():
    lower, upper = nearest_quarter_levels(0.6550, step=0.0025)
    assert lower == 0.6550
    assert upper == 0.6575


def test_quarter_target_long_and_short():
    long_t = quarter_target(0.6543, "long", step=0.0025)
    assert long_t == 0.6550
    short_t = quarter_target(0.6543, "short", step=0.0025)
    assert short_t == 0.6525


def test_quarter_target_n_levels():
    t1 = quarter_target(0.6543, "long", step=0.0025, n_levels=1)
    t2 = quarter_target(0.6543, "long", step=0.0025, n_levels=2)
    assert round(t2 - t1, 10) == 0.0025


def test_add_quarter_context_near_flag():
    df = pd.DataFrame({
        "close": [0.6551, 0.6562],
        "atr": [0.001, 0.001],
    })
    out = add_quarter_context(df, price_col="close", step=0.0025, proximity_atr_frac=0.5)
    assert out.loc[0, "near_quarter_level"]      # 0.6551 está a 0.0001 del cuarto 0.6550
    assert not out.loc[1, "near_quarter_level"]  # 0.6562 está a 0.0012, lejos con threshold 0.0005
