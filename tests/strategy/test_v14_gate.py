"""V14: puerta d1+h4+ny_am alineados; NY PM no es puerta."""
import pandas as pd
from strategy.v14_confluence import gate_v14


def _c(rows):
    return pd.DataFrame(rows, columns=["d1", "h4", "ny_am", "ny_pm"], index=pd.date_range("2026-01-05", periods=len(rows)))


def test_gate_three_aligned_opens_regardless_of_pm():
    g = gate_v14(_c([(1, 1, 1, -1), (1, 1, 1, 0), (-1, -1, -1, -1)]))
    assert list(g.direction) == [1, 1, -1] and set(g.confidence) == {"alta"}


def test_gate_closed_if_any_neutral_or_opposed():
    g = gate_v14(_c([(1, 1, 0, 1), (1, -1, 1, 1), (0, 0, 0, 0)]))
    assert list(g.direction) == [0, 0, 0] and set(g.confidence) == {"na"}
