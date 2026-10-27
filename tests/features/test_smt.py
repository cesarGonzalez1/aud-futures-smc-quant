import numpy as np
import pandas as pd

from data import schema
from features.smt import add_smt_divergence


def _frame(highs: list[float], lows: list[float]) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=len(highs), freq="D", tz="UTC")
    df = pd.DataFrame({
        schema.OPEN: highs, schema.HIGH: highs, schema.LOW: lows, schema.CLOSE: highs,
    }, index=idx)
    df.index.name = schema.TIMESTAMP
    return df


def test_smt_bear_when_a_makes_higher_high_and_b_does_not():
    n = 20
    base = 0.90
    a_high = [base] * n
    a_high[5], a_high[15] = 1.10, 1.20   # 6A: higher high (1.20 > 1.10)
    b_high = [base] * n
    b_high[5], b_high[15] = 1.05, 1.03   # 6N: NO confirma (1.03 < 1.05) -> divergencia bajista

    a = _frame(a_high, [base - 0.5] * n)
    b = _frame(b_high, [base - 0.5] * n)

    out = add_smt_divergence(a, b)
    assert out["smt_bear"].iloc[17]          # swing en i=15 confirmado en j=15+k=17
    assert not out["smt_bull"].any()
    assert out["smt_bear"].sum() == 1        # solo un evento de divergencia


def test_smt_bull_when_a_makes_lower_low_and_b_does_not():
    n = 20
    base = 1.10
    a_low = [base] * n
    a_low[5], a_low[15] = 0.90, 0.80     # 6A: lower low (0.80 < 0.90)
    b_low = [base] * n
    b_low[5], b_low[15] = 0.95, 0.97     # 6N: NO confirma (0.97 > 0.95) -> divergencia alcista

    a = _frame([base + 0.5] * n, a_low)
    b = _frame([base + 0.5] * n, b_low)

    out = add_smt_divergence(a, b)
    assert out["smt_bull"].iloc[17]
    assert not out["smt_bear"].any()


def test_smt_no_divergence_when_both_confirm():
    n = 20
    base = 0.90
    a_high = [base] * n
    a_high[5], a_high[15] = 1.10, 1.20
    b_high = [base] * n
    b_high[5], b_high[15] = 1.05, 1.15   # 6N TAMBIÉN hace higher high -> sin divergencia

    a = _frame(a_high, [base - 0.5] * n)
    b = _frame(b_high, [base - 0.5] * n)

    out = add_smt_divergence(a, b)
    assert not out["smt_bear"].any()
