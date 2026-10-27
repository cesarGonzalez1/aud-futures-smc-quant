"""V12: reglas puras de la spec (buckets, disparador VWAP, RR/zonas)."""

from __future__ import annotations

import pandas as pd
import pytest

from strategy.liquidity_sweep_ifvg_v12 import classify_trigger, resolve_rr_target, time_bucket


@pytest.mark.parametrize("hhmm,exp", [
    ("00:30", "A0"), ("00:55", "A0"), ("01:00", "A"), ("01:59", "A"),
    ("02:00", "B"), ("02:59", "B"), ("03:00", "C"), ("03:55", "C"), ("04:00", "fuera"), ("00:25", "fuera"),
])
def test_time_bucket(hhmm, exp):
    assert time_bucket(pd.Timestamp(f"2024-03-05 {hhmm}", tz="UTC")) == exp


def test_classify_trigger():
    assert classify_trigger(0.66, 0.65, 0.67, True) == "eq_vwap"          # EQ dentro de bandas
    assert classify_trigger(0.67, 0.65, 0.67, True) == "eq_extremo"       # toca banda sup
    assert classify_trigger(0.68, 0.65, 0.67, False) == "sweep_extremo"   # sin EQ, en extremo
    assert classify_trigger(0.66, 0.65, 0.67, False) is None              # sin EQ dentro → no setup
    assert classify_trigger(0.66, float("nan"), 0.67, True) is None       # sin VWAP → no opera


def test_rr_default_without_zones():
    tgt, rr, src = resolve_rr_target(side="long", entry=1.0, stop=0.99, zones=[])
    assert rr == 1.7 and src == "rr_base" and tgt == pytest.approx(1.017)


def test_rr_zone_inside_window_is_used():
    tgt, rr, src = resolve_rr_target(side="short", entry=1.0, stop=1.01, zones=[("pdl", 0.9825)])  # 1.75R
    assert rr == pytest.approx(1.75) and src == "pdl" and tgt == pytest.approx(0.9825)


def test_rr_zone_too_close_clamps_to_1_6_and_far_zone_ignored():
    _, rr_close, _ = resolve_rr_target(side="long", entry=1.0, stop=0.99, zones=[("day_hi", 1.005)])  # 0.5R
    assert rr_close == 1.6
    _, rr_far, src = resolve_rr_target(side="long", entry=1.0, stop=0.99, zones=[("pdh", 1.05)])      # 5R
    assert rr_far == 1.7 and src == "rr_base"


def test_rr_ignores_zones_behind_entry():
    _, rr, src = resolve_rr_target(side="long", entry=1.0, stop=0.99, zones=[("pdl", 0.98)])
    assert rr == 1.7 and src == "rr_base"
