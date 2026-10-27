"""Validación directa del proxy AUD/USD contra el 6A real (ADR-006 + ADR-018).

Hasta ahora, ADR-006 ASUMÍA que el proxy spot AUD/USD (Dukascopy, usado para
los 5 años de backtest de V1-V11) se comporta como el futuro real 6A — nunca
se había comprobado directamente porque no había datos intradía reales de 6A.
Con la ingesta de ADR-018 (Yahoo H1/H4, ~2 años reales) ya hay ventana de
solape para comprobarlo.

Qué mide (en la ventana donde AMBOS existen, típicamente los últimos ~2 años):
    1. Correlación de retornos H1 (lo que realmente importa para MSS/CISD:
       ¿suben y bajan juntos barra a barra?), no solo de niveles de precio
       (los niveles obviamente difieren — 6A cotiza distinto que el spot).
    2. Correlación de rango (high-low) por barra — proxy de si la volatilidad
       intrabar se parece.
    3. Alineación de swings de estructura (`features.structure.add_structure`
       aplicado a ambas series): de los swing highs/lows confirmados en 6A,
       ¿cuántos tienen un swing del mismo signo en AUDUSD dentro de +/- 2
       horas? Esto es lo más cercano a "la estrategia dispararía igual en
       ambas series", más relevante que la correlación de precio en sí.

No es un backtest — es un chequeo de la ASUNCIÓN del proxy, honesto: si la
correlación es alta, ADR-006 queda respaldado con evidencia real por primera
vez. Si es baja, hay que reconsiderar cuánto pesan los 5 años de backtest
sobre el proxy.

Uso:
  python -m analysis.validate_proxy
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from data import ingest, schema
from data.storage import parquet_store
from features import structure


def _load(base: str, symbol: str, timeframe: str) -> pd.DataFrame:
    try:
        return parquet_store.read_dataset(base, symbol, timeframe)
    except FileNotFoundError as exc:
        raise SystemExit(
            f"No encontré {symbol} {timeframe} en data/raw/. Corre `make ingest` primero. Detalle: {exc}"
        ) from exc


def _align(real: pd.DataFrame, proxy: pd.DataFrame) -> pd.DataFrame:
    """Une por timestamp exacto (ambas H1, ancladas a la hora en punto UTC)."""
    r = real[[schema.CLOSE, schema.HIGH, schema.LOW]].rename(columns=lambda c: f"real_{c}")
    p = proxy[[schema.CLOSE, schema.HIGH, schema.LOW]].rename(columns=lambda c: f"proxy_{c}")
    out = r.join(p, how="inner")
    return out.dropna()


def _swing_alignment(real: pd.DataFrame, proxy: pd.DataFrame, *, tolerance_bars: int = 2) -> dict:
    """De los swings CONFIRMADOS de `real`, ¿qué fracción tiene un swing del
    mismo signo en `proxy` dentro de `tolerance_bars` horas? Point-in-time por
    construcción (usa columnas ya confirmadas con retraso de `add_structure`).
    """
    real_s = structure.add_structure(real)
    proxy_s = structure.add_structure(proxy)

    def _match_rate(col: str) -> tuple[int, int]:
        confirmed = real_s.index[real_s[col]]
        if len(confirmed) == 0:
            return 0, 0
        proxy_confirmed = proxy_s.index[proxy_s[col]]
        hits = 0
        for t in confirmed:
            window = proxy_confirmed[(proxy_confirmed >= t - pd.Timedelta(hours=tolerance_bars))
                                      & (proxy_confirmed <= t + pd.Timedelta(hours=tolerance_bars))]
            if len(window) > 0:
                hits += 1
        return hits, len(confirmed)

    hi_hits, hi_total = _match_rate("swing_high_confirmed")
    lo_hits, lo_total = _match_rate("swing_low_confirmed")
    return {
        "swing_high_match_rate": hi_hits / hi_total if hi_total else float("nan"),
        "swing_high_n": hi_total,
        "swing_low_match_rate": lo_hits / lo_total if lo_total else float("nan"),
        "swing_low_n": lo_total,
    }


def main() -> None:
    config = ingest.load_config()
    raw = config["paths"]["raw"]

    real_h1 = _load(raw, "6A", "H1")
    proxy_h1 = _load(raw, "AUDUSD", "H1")

    aligned = _align(real_h1, proxy_h1)
    if aligned.empty:
        raise SystemExit("0 barras solapadas entre 6A real y el proxy AUDUSD — revisa la ingesta.")

    ret_real = aligned["real_close"].pct_change().dropna()
    ret_proxy = aligned["proxy_close"].pct_change().dropna()
    ret_corr = ret_real.corr(ret_proxy)

    range_real = (aligned["real_high"] - aligned["real_low"])
    range_proxy = (aligned["proxy_high"] - aligned["proxy_low"])
    range_corr = range_real.corr(range_proxy)

    swing = _swing_alignment(real_h1.loc[aligned.index[0]:aligned.index[-1]],
                              proxy_h1.loc[aligned.index[0]:aligned.index[-1]])

    print("=== Validación proxy AUDUSD vs 6A real (ADR-006 + ADR-018) ===\n")
    print(f"Ventana solapada: {aligned.index[0]} a {aligned.index[-1]} ({len(aligned)} barras H1)\n")
    print(f"Correlación de retornos H1 (lo que más importa): {ret_corr:.4f}")
    print(f"Correlación de rango intrabar (high-low): {range_corr:.4f}\n")
    print(f"Swing highs confirmados en 6A con match en proxy (±2h): "
          f"{swing['swing_high_match_rate']:.1%} ({swing['swing_high_n']} swings)")
    print(f"Swing lows confirmados en 6A con match en proxy (±2h): "
          f"{swing['swing_low_match_rate']:.1%} ({swing['swing_low_n']} swings)\n")

    if ret_corr >= 0.9:
        veredicto = "ALTA — respalda ADR-006 con evidencia real por primera vez."
    elif ret_corr >= 0.7:
        veredicto = "MODERADA — el proxy se parece, pero no es 1:1; tratar V1-V11 con algo más de cautela."
    else:
        veredicto = "BAJA — reconsiderar cuánto pesan los backtests sobre el proxy."
    print(f"Veredicto: {veredicto}")

    ts = datetime.now(timezone.utc)
    exp = Path(config["paths"]["experiments"]) / f"{ts.date().isoformat()}_validate_proxy_vs_6a_real"
    exp.mkdir(parents=True, exist_ok=True)
    (exp / "report.md").write_text(
        f"# Validación proxy AUDUSD vs 6A real (ADR-006+018) — {ts.date().isoformat()}\n\n"
        f"Ventana: {aligned.index[0]} a {aligned.index[-1]} ({len(aligned)} barras H1)\n\n"
        f"- Correlación de retornos H1: {ret_corr:.4f}\n"
        f"- Correlación de rango intrabar: {range_corr:.4f}\n"
        f"- Match swing highs (±2h): {swing['swing_high_match_rate']:.1%} ({swing['swing_high_n']} swings)\n"
        f"- Match swing lows (±2h): {swing['swing_low_match_rate']:.1%} ({swing['swing_low_n']} swings)\n\n"
        f"Veredicto: {veredicto}\n",
        encoding="utf-8")
    print(f"\nGuardado en: {exp}")


if __name__ == "__main__":
    main()
