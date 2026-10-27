"""Gestión de riesgo — tamaño de posición + frenos de circuito (ADR-019).

Brecha real encontrada al investigar cómo funcionan sistemas que sí operan en
cuentas de fondeo: este proyecto, hasta ahora, mide todo en R (múltiplos de
riesgo) pero NUNCA calcula cuánto arriesgar en dólares reales, y no tiene
ningún freno automático tras una racha de pérdidas. La investigación es
consistente en esto — no es un detalle menor:

    "~95% de las evaluaciones de cuentas de fondeo fallan por mala gestión de
    riesgo, no por estrategias malas" (fuente: quantvps.com, 2026-02-16).
    Ejemplo real citado: evaluación FTMO de $100k completada arriesgando 0.75%
    por operación y DETENIÉNDOSE tras 2 pérdidas consecutivas.

Esto separa la SEÑAL (qué operar, decision_engine/live_signal.py) del RIESGO
(cuánto arriesgar, y cuándo dejar de operar del todo) — dos capas distintas,
igual que cualquier sistema institucional (ver investigación citada: "position
sizing" y "riesgo de portafolio" son responsabilidad separada de la señal).

**Honesto:** con V9 todavía neta negativa (-0.119R), ninguna forma de
position sizing hace rentable una estrategia que no lo es — position sizing
protege el capital y suaviza la curva, no genera edge donde no lo hay. Se
implementa igual porque es la infraestructura que faltará el día que sí haya
una versión positiva, y porque los frenos de circuito (parte 2) importan
incluso con una estrategia negativa: limitan cuánto se pierde mientras se seguí
iterando.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

__all__ = ["position_size", "score_adjusted_risk_pct", "CircuitBreaker", "PositionSizeResult"]


@dataclass
class PositionSizeResult:
    contracts: int
    risk_amount: float
    risk_pct_used: float
    risk_per_contract: float
    capped_by_min_contract: bool = False


def position_size(
    *,
    account_equity: float,
    risk_pct: float,
    entry_price: float,
    stop_price: float,
    contract_multiplier: float,
    max_contracts: int | None = None,
) -> PositionSizeResult:
    """Tamaño de posición fraccional-fijo (fixed-fractional, el método base de
    toda la literatura de risk management citada): arriesga `risk_pct` del
    equity, dado el stop de la señal.

    Para 6A (CME): `contract_multiplier` = 100_000 (tamaño del contrato en AUD;
    el riesgo en USD por contrato es `|entry-stop| * 100_000`).

    Redondea HACIA ABAJO (nunca arriesga más de lo pedido). Si el riesgo por
    contrato ya excede el riesgo permitido, devuelve 0 contratos — no hay
    "size mínimo forzado" que viole el % de riesgo pedido.
    """
    if risk_pct <= 0 or account_equity <= 0:
        raise ValueError("account_equity y risk_pct deben ser positivos")
    risk_per_unit = abs(entry_price - stop_price)
    if risk_per_unit <= 0:
        raise ValueError("entry_price y stop_price no pueden ser iguales")

    risk_amount = account_equity * risk_pct
    risk_per_contract = risk_per_unit * contract_multiplier
    contracts = math.floor(risk_amount / risk_per_contract + 1e-9)  # tolerancia a error de punto flotante
    capped = False
    if max_contracts is not None and contracts > max_contracts:
        contracts = max_contracts
        capped = True

    return PositionSizeResult(
        contracts=max(contracts, 0), risk_amount=risk_amount, risk_pct_used=risk_pct,
        risk_per_contract=risk_per_contract, capped_by_min_contract=capped,
    )


def score_adjusted_risk_pct(
    score: float,
    *,
    base_risk_pct: float = 0.0075,  # 0.75%, el mismo valor del caso real citado (FTMO)
    score_floor: float = -1.0,
    score_ceiling: float = 0.5,
    min_mult: float = 0.5,
    max_mult: float = 1.5,
) -> float:
    """Escala el riesgo base según la confianza del score de confluencia
    (`decision_engine.scoring.ConfluenceScorer`) — más confianza, más tamaño;
    menos confianza, menos tamaño, NUNCA cero solo por score bajo (el gate de
    tomar o no el trade ya lo decide `live_signal`, esto solo ajusta cuánto).

    Interpola linealmente `score` dentro de [`score_floor`, `score_ceiling`]
    hacia un multiplicador en [`min_mult`, `max_mult`], recortado a los bordes.
    """
    if score_ceiling <= score_floor:
        raise ValueError("score_ceiling debe ser mayor que score_floor")
    frac = (score - score_floor) / (score_ceiling - score_floor)
    frac = min(max(frac, 0.0), 1.0)
    mult = min_mult + frac * (max_mult - min_mult)
    return base_risk_pct * mult


@dataclass
class CircuitBreaker:
    """Frenos de circuito (ADR-019): réplica del patrón real citado en la
    investigación (evaluación FTMO real: 0.75%/trade, freno tras 2 pérdidas
    seguidas). Rastrea el estado de la sesión — quien llama es responsable de
    actualizarlo después de cada operación cerrada.
    """

    max_consecutive_losses: int = 2
    max_daily_loss_r: float = 2.0
    max_trades_per_day: int = 1  # ya es la regla de "una posición a la vez" del proyecto (V1-V11)

    consecutive_losses: int = field(default=0, init=False)
    daily_r: float = field(default=0.0, init=False)
    trades_today: int = field(default=0, init=False)

    def register_trade(self, r_multiple: float) -> None:
        self.trades_today += 1
        self.daily_r += r_multiple
        if r_multiple < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def reset_day(self) -> None:
        self.daily_r = 0.0
        self.trades_today = 0
        # consecutive_losses NO se resetea al cambiar de día a propósito: una
        # racha que cruza la medianoche sigue siendo la misma racha.

    def can_trade(self) -> tuple[bool, str]:
        if self.consecutive_losses >= self.max_consecutive_losses:
            return False, (
                f"{self.consecutive_losses} pérdidas consecutivas >= límite "
                f"({self.max_consecutive_losses}) — parar, no es mala suerte aleatoria, "
                f"es la señal de revisar antes de seguir arriesgando capital real."
            )
        if self.daily_r <= -abs(self.max_daily_loss_r):
            return False, (
                f"pérdida del día ({self.daily_r:.2f}R) alcanzó el límite diario "
                f"(-{abs(self.max_daily_loss_r)}R) — parar por hoy."
            )
        if self.trades_today >= self.max_trades_per_day:
            return False, f"ya se tomaron {self.trades_today} operaciones hoy (límite {self.max_trades_per_day})."
        return True, "ok"
