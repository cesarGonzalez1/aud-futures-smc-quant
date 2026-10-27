import pandas as pd

from strategy.liquidity_sweep_ifvg_v10 import filter_trades_by_smt


def _smt_daily(rows: dict) -> pd.DataFrame:
    idx = pd.DatetimeIndex(list(rows.keys()), tz="UTC", name="timestamp")
    return pd.DataFrame(
        {"smt_bear": [v[0] for v in rows.values()], "smt_bull": [v[1] for v in rows.values()]},
        index=idx,
    )


def test_filter_keeps_only_aligned_smt_days():
    trades = pd.DataFrame({
        "entry_time": [
            "2024-01-02T01:00:00+00:00",  # short, smt_bear=True -> se queda
            "2024-01-03T01:00:00+00:00",  # short, smt_bear=False -> se descarta
            "2024-01-04T01:00:00+00:00",  # long, smt_bull=True -> se queda
        ],
        "side": ["short", "short", "long"],
    })
    smt_daily = _smt_daily({
        pd.Timestamp("2024-01-02", tz="UTC"): (True, False),
        pd.Timestamp("2024-01-03", tz="UTC"): (False, False),
        pd.Timestamp("2024-01-04", tz="UTC"): (False, True),
    })

    out = filter_trades_by_smt(trades, smt_daily)
    assert len(out) == 2
    assert set(out["entry_time"]) == {"2024-01-02T01:00:00+00:00", "2024-01-04T01:00:00+00:00"}


def test_filter_drops_days_missing_from_smt_daily():
    trades = pd.DataFrame({"entry_time": ["2024-05-05T01:00:00+00:00"], "side": ["short"]})
    smt_daily = _smt_daily({pd.Timestamp("2024-01-02", tz="UTC"): (True, True)})
    out = filter_trades_by_smt(trades, smt_daily)
    assert out.empty


def test_filter_empty_trades_passthrough():
    trades = pd.DataFrame({"entry_time": [], "side": []})
    smt_daily = _smt_daily({pd.Timestamp("2024-01-02", tz="UTC"): (True, True)})
    out = filter_trades_by_smt(trades, smt_daily)
    assert out.empty
