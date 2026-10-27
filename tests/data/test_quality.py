"""Tests de validación de calidad (ADR-001, sección 13).

Cada test parte de un dataset limpio conocido y le inyecta UN defecto específico,
verificando que el chequeo correspondiente lo detecta y ninguno más lo enmascara.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from data import schema
from data.validation import quality


def test_clean_dataset_is_valid(clean_h1):
    report = quality.validate(clean_h1, "H1")
    assert report.is_valid
    assert not report.errors


def test_detects_duplicate_timestamps(clean_h1):
    dup = pd.concat([clean_h1, clean_h1.iloc[[0]]]).sort_index()
    report = quality.check_index(dup)
    assert not report.is_valid
    assert any("duplicad" in e for e in report.errors)


def test_detects_unordered_index(clean_h1):
    shuffled = clean_h1.iloc[::-1]
    report = quality.check_index(shuffled)
    assert any("ordenado" in e for e in report.errors)


def test_detects_naive_index(clean_h1):
    naive = clean_h1.tz_localize(None)
    report = quality.check_index(naive)
    assert any("UTC" in e for e in report.errors)


def test_detects_high_below_low(clean_h1):
    bad = clean_h1.copy()
    bad.iloc[5, bad.columns.get_loc(schema.HIGH)] = bad[schema.LOW].iloc[5] - 1
    report = quality.check_ohlc_coherence(bad)
    assert any("high < low" in e for e in report.errors)


def test_detects_null_in_ohlc(clean_h1):
    bad = clean_h1.copy()
    bad.iloc[3, bad.columns.get_loc(schema.CLOSE)] = np.nan
    report = quality.check_ohlc_coherence(bad)
    assert any("nulos" in e for e in report.errors)


def test_small_gap_is_warning_not_error(clean_h1):
    # Una barra faltante es un problema de completitud, no de validez => warning.
    gapped = clean_h1.drop(clean_h1.index[10])
    report = quality.check_gaps(gapped, "H1", weekend_gap_allowed=True)
    assert report.is_valid
    assert any("Hueco" in w for w in report.warnings)


def test_large_gap_is_error(clean_h1):
    # Pérdida gruesa: borro barras suficientes para superar error_gap_days a mitad
    # de semana (el clean_h1 empieza lunes, así que el hueco no es de fin de semana).
    gapped = clean_h1.drop(clean_h1.index[5:35])
    report = quality.check_gaps(gapped, "H1", weekend_gap_allowed=True, error_gap_days=1.0)
    assert not report.is_valid
    assert any("gruesa" in e for e in report.errors)


def test_price_outlier_is_warning_not_error(clean_h1):
    spiked = clean_h1.copy()
    spiked.iloc[20, spiked.columns.get_loc(schema.CLOSE)] *= 1.5  # salto enorme
    report = quality.check_price_outliers(spiked, zscore_threshold=8.0)
    assert report.is_valid  # outlier no invalida, solo advierte
    assert report.warnings
