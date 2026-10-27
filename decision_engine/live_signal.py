"""Motor de señales — modo VIVO (ADR-017, parte 2).

Hasta ahora todo el proyecto corría en modo backtest: escanea 5 años de
historia y cuenta resultados. Esto es lo que pediste como "asistente": evaluar
la barra MÁS RECIENTE (hoy) y devolver Long/Short/No-Trade con
entrada/stop/target y un score de confianza — para correr cada tarde durante
tu killzone y usarlo como segunda opinión, ejecutando tú manualmente.

**Cómo funciona (reutiliza V9 al 100%, no reimplementa nada):**
Corre `strategy.liquidity_sweep_ifvg_v7.generate_trades_v7` (con
`confirmation_require="mss"`, igual que V9) sobre el historial que le pases —
en vivo, eso es "los últimos N días de M5/H1", no 5 años — y se queda con la
ÚLTIMA señal generada, si su hora de entrada cae dentro de `lookback_hours`
respecto al momento de evaluación (`as_of`). Si no hay ninguna señal así de
reciente, es No-Trade explícito (no se inventa una entrada solo porque no hay
nada mejor que ofrecer).

**Limitación honesta de este v1:** si no hay señal, el diagnóstico de "por
qué" (¿no hubo sweep? ¿no confirmó MSS? ¿no hubo IFVG?) no está implementado
todavía — devuelve "sin señal en la ventana", no la razón capa por capa. Eso
queda como mejora futura, no se aproxima aquí.

**Requiere datos frescos:** el usuario debe correr `make ingest` (o una
actualización más ligera, a implementar) antes de cada evaluación para que
`m5`/`h1` incluyan la barra de hoy — este módulo NO descarga datos, solo evalúa
lo que se le pasa.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from decision_engine.risk_manager import CircuitBreaker, position_size, score_adjusted_risk_pct
from decision_engine.scoring import ConfluenceScorer
from features.mss_cisd import add_mss_flags
from strategy.liquidity_sweep_ifvg_v7 import generate_trades_v7, trades_to_frame

__all__ = ["Signal", "evaluate_latest"]


@dataclass
class Signal:
    """Salida del motor de señales para un momento dado (`as_of`)."""

    as_of: pd.Timestamp
    has_signal: bool
    side: str | None = None
    entry_price: float | None = None
    stop: float | None = None
    target: float | None = None
    confirmation_source: str | None = None
    target_source: str | None = None
    score: float | None = None
    entry_time: pd.Timestamp | None = None
    reason: str = ""
    suggested_contracts: int | None = None
    risk_pct_used: float | None = None
    circuit_breaker_ok: bool = True
    circuit_breaker_reason: str = ""

    def summary(self) -> str:
        if not self.has_signal:
            return f"[{self.as_of}] NO-TRADE — {self.reason}"
        base = (
            f"[{self.as_of}] {self.side.upper()} — entrada={self.entry_price:.5f} "
            f"stop={self.stop:.5f} target={self.target:.5f} "
            f"score={self.score:.3f} (confirmación={self.confirmation_source}, "
            f"target={self.target_source}, señal generada {self.entry_time})"
        )
        if not self.circuit_breaker_ok:
            return base + f"\n⛔ FRENO DE CIRCUITO ACTIVO — {self.circuit_breaker_reason} (NO operar pese a la señal)"
        if self.suggested_contracts is not None:
            base += f"\nTamaño sugerido: {self.suggested_contracts} contrato(s) (riesgo {self.risk_pct_used:.2%} del equity)"
        return base


def evaluate_latest(
    m5: pd.DataFrame,
    h1: pd.DataFrame,
    confluence: pd.DataFrame,
    scorer: ConfluenceScorer,
    *,
    as_of: pd.Timestamp | None = None,
    lookback_hours: float = 6.0,
    window_start: int = 0,
    window_end: int = 4,
    account_equity: float | None = None,
    contract_multiplier: float = 100_000.0,
    base_risk_pct: float = 0.0075,
    max_contracts: int | None = None,
    circuit_breaker: CircuitBreaker | None = None,
) -> Signal:
    """Evalúa si hay una señal V9 vigente al momento `as_of` (default: la
    última barra de `m5`).

    Args:
        m5, h1, confluence: mismo formato que `backtest.run_v7._prepare` —
            quien llama es responsable de que `m5`/`h1` estén actualizados
            (`make ingest` reciente) y tengan las features ya calculadas
            (estructura, IFVG, régimen, etc. — igual que para backtest).
        scorer: `ConfluenceScorer` YA calibrado (`ConfluenceScorer.fit`) sobre
            histórico — este módulo no calibra nada, solo aplica.
        lookback_hours: cuánto puede tener de "vieja" la señal para seguir
            considerándose vigente (una señal de hace 3 días no sirve para
            operar hoy).
        account_equity: si se da (ADR-019), calcula tamaño de posición
            sugerido (`decision_engine.risk_manager.position_size`), con el
            riesgo ajustado por la confianza del score
            (`score_adjusted_risk_pct`). Si es `None`, no sugiere tamaño (solo
            señal + score, comportamiento igual que antes de ADR-019).
        circuit_breaker: si se da, se consulta `can_trade()` — si está
            activo, la señal se marca explícitamente para NO operar aunque
            las condiciones de V9 se cumplan (ADR-019: la señal y el permiso
            para operar son capas separadas).
    """
    as_of = as_of or m5.index[-1]
    m5_scored = add_mss_flags(m5) if "mss_bull" not in m5.columns else m5

    trades, confidences, sources, confirmations, quarter_aligned = generate_trades_v7(
        m5_scored, h1, confluence, window_start=window_start, window_end=window_end,
        confirmation_require="mss",
    )
    if not trades:
        return Signal(as_of=as_of, has_signal=False, reason="ninguna señal V9 en todo el histórico provisto")

    df = trades_to_frame(trades, confidences, sources, confirmations, quarter_aligned)
    df["entry_time"] = pd.to_datetime(df["entry_time"])
    last = df.iloc[-1]

    age = as_of - last["entry_time"]
    if age > pd.Timedelta(hours=lookback_hours) or age < pd.Timedelta(0):
        return Signal(
            as_of=as_of, has_signal=False,
            reason=f"la última señal fue {last['entry_time']} (hace {age}), fuera de la ventana de "
                   f"{lookback_hours}h — no está vigente para operar ahora",
        )

    score = scorer.score_row(last)

    cb_ok, cb_reason = (True, "") if circuit_breaker is None else circuit_breaker.can_trade()

    suggested_contracts = None
    risk_pct_used = None
    if account_equity is not None:
        risk_pct_used = score_adjusted_risk_pct(score, base_risk_pct=base_risk_pct)
        sizing = position_size(
            account_equity=account_equity, risk_pct=risk_pct_used,
            entry_price=float(last["entry_price"]), stop_price=float(last["stop"]),
            contract_multiplier=contract_multiplier, max_contracts=max_contracts,
        )
        suggested_contracts = sizing.contracts

    return Signal(
        as_of=as_of, has_signal=True, side=last["side"], entry_price=float(last["entry_price"]),
        stop=float(last["stop"]), target=float(last["target"]),
        confirmation_source=last["confirmation_source"], target_source=last["target_source"],
        score=float(score), entry_time=last["entry_time"],
        reason="señal V9 vigente",
        suggested_contracts=suggested_contracts, risk_pct_used=risk_pct_used,
        circuit_breaker_ok=cb_ok, circuit_breaker_reason=cb_reason,
    )
