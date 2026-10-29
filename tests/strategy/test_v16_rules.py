"""V16: 3 velas seguidas (puras) y recálculo de lookback."""
import numpy as np
from strategy.liquidity_sweep_ifvg_v16 import three_candle_signal


def test_three_bearish_candles_short():
    o = np.array([1.0, 1.0, 1.0, 1.0, 1.0]); c = np.array([1.01, 0.99, 0.99, 0.98, 1.02])
    assert three_candle_signal(o, c, 0, 4, "short") == 3        # velas 1,2,3 bajistas


def test_broken_run_does_not_count_and_none_if_absent():
    o = np.array([1.0] * 6); c = np.array([0.99, 0.99, 1.01, 0.99, 0.99, 1.01])
    assert three_candle_signal(o, c, 0, 5, "short") is None     # la racha se rompe antes de 3


def test_long_needs_bullish_closes_and_respects_window_start():
    o = np.array([1.0] * 5); c = np.array([1.01, 1.01, 1.01, 0.99, 1.01])
    assert three_candle_signal(o, c, 0, 4, "long") == 2
    assert three_candle_signal(o, c, 1, 4, "long") is None      # arrancando en 1 solo hay 2 seguidas
