"""V15: >=2 a favor y ninguno en contra; NY PM no es puerta."""
import pandas as pd
from strategy.v15_confluence import gate_v15


def _c(rows):
    return pd.DataFrame(rows, columns=["d1", "h4", "ny_am", "ny_pm"], index=pd.date_range("2026-01-05", periods=len(rows)))


def test_opens_with_three_or_two_plus_neutral():
    g = gate_v15(_c([(1, 1, 1, -1), (1, 1, 0, 0), (-1, 0, -1, 1), (0, -1, -1, 0)]))
    assert list(g.direction) == [1, 1, -1, -1]
    assert list(g.gate_tipo) == ["tres", "dos_neutral", "dos_neutral", "dos_neutral"]


def test_closed_if_any_opposed_or_only_one_vote():
    g = gate_v15(_c([(1, 1, -1, 1), (1, 0, 0, 1), (0, 0, 0, 0), (1, -1, 0, 1)]))
    assert list(g.direction) == [0, 0, 0, 0] and set(g.gate_tipo) == {"cerrada"} and set(g.confidence) == {"na"}
