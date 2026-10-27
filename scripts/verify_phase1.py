"""Verificación post-pull de Fase 1 (no basta con "terminó sin error").

Corre sobre los datasets REALES ya escritos en data/raw:
  1. Verifica sha256 de cada manifest contra el Parquet real en disco.
  2. Re-corre la validación de calidad de cada target y clasifica errors/warnings.
  3. Reporta conteo de filas real vs. esperado aproximado (mercado abierto).

Uso:  python -m scripts.verify_phase1
"""

from __future__ import annotations

from collections import Counter

from data import ingest
from data.storage import manifest as M
from data.storage import parquet_store
from data.validation import quality

# Targets de Fase 1 (symbol, timeframe).
TARGETS = [
    ("AUDUSD", "H1"),
    ("AUDUSD", "D1"),
    ("XAUUSD", "H1"),
    ("XAUUSD", "D1"),
    ("DXY", "D1"),
]

# Esperado aproximado por año de mercado abierto (para comparar, no para asumir):
#   H1 forex 24h × 5 días × ~52 semanas ≈ 6240/año (≈31k en 5 años).
#   D1 ≈ 260 días hábiles/año (≈1300 en 5 años).
YEARS = 5.0
EXPECTED_PER_YEAR = {"H1": 6240, "D1": 260}


def _warning_categories(warnings: list[str]) -> Counter:
    """Agrupa warnings de huecos por categoría legible."""
    cats: Counter = Counter()
    for w in warnings:
        if "fin de semana" in w:
            cats["fin_de_semana"] += 1
        elif "Outlier" in w:
            cats["outlier_precio"] += 1
        elif "Hueco" in w:
            cats["hueco_intradia"] += 1
        else:
            cats["otro"] += 1
    return cats


def main() -> int:
    config = ingest.load_config()
    raw_base = config["paths"]["raw"]
    quality_cfg = config.get("quality", {})

    print("=== Verificación post-pull Fase 1 (5 años, datos reales) ===\n")
    all_ok = True

    for symbol, timeframe in TARGETS:
        directory = parquet_store.dataset_dir(raw_base, symbol, timeframe)
        if not (directory / "manifest.json").exists():
            print(f"  ✗ {symbol} {timeframe}: FALTA manifest/dataset")
            all_ok = False
            continue

        man = M.read_manifest(directory)
        sha_ok = M.verify(directory, parquet_store.PARQUET_NAME)
        df = parquet_store.read_dataset(raw_base, symbol, timeframe)

        report = quality.validate(
            df,
            timeframe,
            zscore_threshold=quality_cfg.get("price_outlier_zscore", 8.0),
            weekend_gap_allowed=quality_cfg.get("weekend_gap_allowed", True),
            error_gap_bars=quality_cfg.get("error_gap_bars", 24),
        )

        expected = int(EXPECTED_PER_YEAR[timeframe] * YEARS)
        pct = 100.0 * man.row_count / expected if expected else 0.0
        cats = _warning_categories(report.warnings)

        status = "✓" if (sha_ok and report.is_valid) else "✗"
        if not (sha_ok and report.is_valid):
            all_ok = False

        print(f"  {status} {symbol:7} {timeframe:3}")
        print(f"      filas={man.row_count:>7}  esperado≈{expected:>7} ({pct:5.1f}% mercado abierto)")
        print(f"      rango={man.date_range[0]}..{man.date_range[1]}  sha256_verify={sha_ok}")
        print(f"      spread_medio={df['spread'].dropna().mean():.5f}" if "spread" in df.columns else "      (sin spread)")
        print(f"      errores={len(report.errors)}  warnings={len(report.warnings)} {dict(cats)}")
        for e in report.errors[:5]:
            print(f"        ERROR: {e}")
        print()

    print("=== RESULTADO:", "TODO OK" if all_ok else "HAY FALLOS", "===")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
