"""Motor de señales — CLI para correr cada tarde (ADR-017).

Recalibra el `ConfluenceScorer` con TODO tu histórico (V9: jerarquía completa +
confirmación MSS-only) y evalúa si hay una señal vigente ahora mismo. Pensado
para correr cada tarde, dentro de tu ventana de preparación (5-8pm CDMX) o ya
en la killzone (8-10pm CDMX) — evalúa la barra más reciente que tengas ingerida.

**Antes de correr esto, corre `make ingest`** para que M5/H1 tengan la barra de
hoy — este script NO descarga datos nuevos, solo evalúa lo que ya está en
`data/raw/`.

Uso:
  python -m decision_engine.run_signal
  python -m decision_engine.run_signal --lookback-hours 4
"""

from __future__ import annotations

import sys

from backtest import metrics
from backtest.run_v5 import _prepare
from data import ingest
from decision_engine.live_signal import evaluate_latest
from decision_engine.scoring import SCORE_FEATURES, ConfluenceScorer
from features.mss_cisd import add_mss_flags
from strategy.liquidity_sweep_ifvg_v7 import generate_trades_v7, trades_to_frame


def main() -> None:
    lookback_hours = 6.0
    if "--lookback-hours" in sys.argv:
        lookback_hours = float(sys.argv[sys.argv.index("--lookback-hours") + 1])

    config = ingest.load_config()
    print("Cargando histórico y recalibrando el score de confluencia (V9 + ConfluenceScorer)...")
    m5, h1, confluence, man, (window_start, window_end) = _prepare(config, None)
    m5 = add_mss_flags(m5)

    half_spread = float(m5["spread"].dropna().mean()) / 2.0 if "spread" in m5.columns else 0.0
    atr_ref = float(m5["atr"].dropna().median()) if "atr" in m5.columns else 0.0

    trades, confidences, sources, confirmations, quarter_aligned = generate_trades_v7(
        m5, h1, confluence, window_start=window_start, window_end=window_end,
        confirmation_require="mss",
    )
    if not trades:
        print("No hay histórico suficiente para calibrar el score (0 operaciones V9). Corre `make ingest` primero.")
        return

    hist = trades_to_frame(trades, confidences, sources, confirmations, quarter_aligned)
    hist = metrics.apply_costs(hist, half_spread=half_spread, slippage_atr_frac=0.05, atr=atr_ref)
    scorer = ConfluenceScorer.fit(hist, features=SCORE_FEATURES)
    print(f"Score calibrado con {len(hist)} operaciones históricas (V9, dataset: {man.sha256[:12]}...).\n")

    signal = evaluate_latest(
        m5, h1, confluence, scorer,
        lookback_hours=lookback_hours, window_start=window_start, window_end=window_end,
        account_equity=50_000, contract_multiplier=100_000, max_contracts=3,
    )
    print("=" * 70)
    print(signal.summary())
    print("=" * 70)
    if signal.has_signal:
        print(
            "\n⚠️  Esto es un ASISTENTE (ADR-015/017), no ejecuta nada por ti. "
            "V9 es net negativo en backtest (-0.119R) — usa esto como segunda "
            "opinión de tu propio análisis, no como señal ciega.\n"
            "Tamaño de posición calculado sobre una cuenta de ejemplo de $50,000 "
            "(ajusta `account_equity`/`max_contracts` en el script a tu cuenta real)."
        )


if __name__ == "__main__":
    main()
