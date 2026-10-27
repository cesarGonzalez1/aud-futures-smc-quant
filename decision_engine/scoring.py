"""Motor de señales — score de confluencia (ADR-017).

Pivote pedido por el usuario: en vez de seguir iterando reglas booleanas
rígidas (V7→V10, cada una un interruptor todo-o-nada que colapsaba la muestra
o la inflaba de golpe), se trata cada atributo ya grabado por operación como
una señal de calidad continua — la práctica real de la industria
("confluence scoring" en vez de AND rígido; ver investigación externa citada
en la conversación: sistemas ML/score usados como filtro de confianza sobre
una base de reglas discrecionales, no como reemplazo de ellas).

**Metodología (validada fuera de muestra antes de usarse):**
1. Pesos = promedio de `r_net` por categoría, calculados SOLO con el periodo
   de entrenamiento (2020-2023) del dataset de V7 (197 operaciones, MSS+CISD).
2. Validación: aplicar esos pesos (fijos, del train) a 2024-2025 (test, nunca
   visto durante el ajuste) y confirmar que ordenar por score mejora la
   expectativa fuera de muestra. Resultado real: el 50% superior por score en
   test pasa de expectancy -0.271R (las 62 operaciones de test completas) a
   -0.078R — mejora real y generalizable, no un ajuste post-hoc sobre el mismo
   dato que se usó para calibrar.
3. Para producción, los pesos se recalculan sobre TODO el histórico disponible
   (197 operaciones) — práctica estándar (validar la metodología con holdout,
   luego reentrenar con todos los datos para desplegar).

**Honestidad de datos:** con 197 operaciones y 5 features categóricas, esto
es un modelo aditivo simple (promedios por grupo), NO una red neuronal ni un
modelo con muchos parámetros — con esta cantidad de datos, cualquier modelo
más complejo se sobreajustaría. A medida que se acumule más historial (más
años de backtest, o trades reales del motor en modo señal), este módulo debe
recalibrarse — los pesos aquí NO son definitivos.

**Sigue siendo net negativo.** Esto no es un sistema listo para operar solo —
es la infraestructura del motor de señales que califica cada setup con un
score y una confianza, en vez de un simple Sí/No.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

__all__ = ["ConfluenceScorer", "LogisticConfluenceScorer", "SCORE_FEATURES"]

#: Atributos usados como señal de calidad (deben existir como columnas en el
#: DataFrame de operaciones, p.ej. la salida de
#: `strategy.liquidity_sweep_ifvg_v7.trades_to_frame`).
SCORE_FEATURES: list[str] = ["confidence", "confirmation_source", "quarter_aligned", "target_source", "side"]


@dataclass
class ConfluenceScorer:
    """Score aditivo de confluencia: suma el `r_net` promedio histórico de
    cada categoría presente en la operación/señal.

    Uso:
        scorer = ConfluenceScorer.fit(train_trades)          # calibración
        scorer.evaluate_out_of_sample(test_trades)           # validación honesta
        scorer_prod = ConfluenceScorer.fit(all_trades)        # producción
        score = scorer_prod.score_row({"confidence": "baja", ...})
    """

    weights: dict[str, dict[str, float]] = field(default_factory=dict)
    features: list[str] = field(default_factory=lambda: list(SCORE_FEATURES))

    @classmethod
    def fit(cls, trades: pd.DataFrame, features: list[str] | None = None) -> "ConfluenceScorer":
        """Calibra pesos = `r_net` promedio por categoría, usando SOLO `trades`
        (quien llama decide si eso es el train, o todo el histórico para
        producción — este método no distingue, es responsabilidad de quien
        arma el split no filtrar datos del futuro dentro de `trades`).
        """
        feats = features or list(SCORE_FEATURES)
        weights = {f: trades.groupby(f)["r_net"].mean().to_dict() for f in feats if f in trades.columns}
        return cls(weights=weights, features=list(weights.keys()))

    def score_row(self, row: dict | pd.Series) -> float:
        """Score = suma de los pesos de cada feature presente en `row`.
        Categorías no vistas durante `fit` aportan 0 (neutral, no penaliza ni
        premia lo desconocido).
        """
        return sum(self.weights.get(f, {}).get(row.get(f) if isinstance(row, dict) else row[f], 0.0)
                    for f in self.features)

    def score_frame(self, trades: pd.DataFrame) -> pd.Series:
        return trades.apply(self.score_row, axis=1)

    def evaluate_out_of_sample(self, test_trades: pd.DataFrame, *, top_pct: float = 0.5) -> dict:
        """Aplica los pesos YA calibrados (de `fit` sobre otro periodo) a
        `test_trades`, se queda con el `top_pct` de mayor score y reporta
        win_rate/expectancy — la forma honesta de saber si el score generaliza,
        NO recalibra nada con `test_trades`.
        """
        scored = test_trades.copy()
        scored["score"] = self.score_frame(scored)
        threshold = scored["score"].quantile(1 - top_pct)
        kept = scored[scored["score"] >= threshold]
        return {
            "n_total": len(test_trades),
            "n_kept": len(kept),
            "threshold": float(threshold),
            "win_rate": float((kept["r_net"] > 0).mean()) if len(kept) else float("nan"),
            "expectancy": float(kept["r_net"].mean()) if len(kept) else float("nan"),
        }


@dataclass
class LogisticConfluenceScorer:
    """Alternativa a `ConfluenceScorer`: regresión logística (one-hot + L2)
    sobre las mismas features categóricas, prediciendo P(ganar) en vez de
    sumar promedios de grupo. ADR-019 — motivación: con más features o
    interacciones, el score aditivo simple puede quedarse corto (no capta
    interacciones entre features); la regresión logística sí puede, al costo
    de más parámetros a estimar con la misma muestra chica (117-197 ops).

    NO se usa a ciegas solo por ser "más ML" — `evaluate_out_of_sample` mide
    exactamente igual que `ConfluenceScorer`, para comparar ambas de forma
    honesta antes de preferir una sobre otra (ver
    `backtest/run_confluence_score.py`).

    Regularización fuerte por defecto (`C=0.3`) — con ~150 operaciones y 5
    features categóricas (~15-20 columnas tras one-hot), un modelo poco
    regularizado se sobreajusta con facilidad.

    **Resultado real (ADR-019, validado fuera de muestra igual que el aditivo):**
    en la misma comparación train(2020-2023)/test(2024-2025) de V7, el score
    aditivo dio -0.059R en el 50% superior; ESTE modelo dio -0.354R — PEOR que
    no filtrar nada (-0.271R sin filtro). Incluso con C=0.3, ~135 operaciones de
    entrenamiento no alcanzan para un modelo con más parámetros (one-hot de 5
    features categóricas) sin sobreajustar. CONCLUSIÓN: se mantiene
    `ConfluenceScorer` (aditivo) como score de producción; esta clase queda
    disponible para cuando haya sustancialmente más datos (cientos-miles de
    operaciones), no se usa todavía.
    """

    model: object | None = field(default=None, repr=False)
    encoder: object | None = field(default=None, repr=False)
    features: list[str] = field(default_factory=lambda: list(SCORE_FEATURES))
    C: float = 0.3

    @classmethod
    def fit(cls, trades: pd.DataFrame, features: list[str] | None = None, *, C: float = 0.3) -> "LogisticConfluenceScorer":
        from sklearn.linear_model import LogisticRegression
        from sklearn.preprocessing import OneHotEncoder

        feats = [f for f in (features or SCORE_FEATURES) if f in trades.columns]
        encoder = OneHotEncoder(handle_unknown="ignore")
        X = encoder.fit_transform(trades[feats].astype(str))
        y = (trades["r_net"] > 0).astype(int)

        model = LogisticRegression(C=C, max_iter=1000, class_weight="balanced")
        model.fit(X, y)
        return cls(model=model, encoder=encoder, features=feats, C=C)

    def score_row(self, row: dict | pd.Series) -> float:
        """P(ganar) predicha — mayor es mejor, igual semántica de ranking que
        `ConfluenceScorer.score_row` aunque la escala sea distinta (0-1, no R)."""
        values = {f: [row.get(f) if isinstance(row, dict) else row[f]] for f in self.features}
        X = self.encoder.transform(pd.DataFrame(values).astype(str))
        return float(self.model.predict_proba(X)[0, 1])

    def score_frame(self, trades: pd.DataFrame) -> pd.Series:
        X = self.encoder.transform(trades[self.features].astype(str))
        proba = self.model.predict_proba(X)[:, 1]
        return pd.Series(proba, index=trades.index)

    def evaluate_out_of_sample(self, test_trades: pd.DataFrame, *, top_pct: float = 0.5) -> dict:
        scored = test_trades.copy()
        scored["score"] = self.score_frame(scored)
        threshold = scored["score"].quantile(1 - top_pct)
        kept = scored[scored["score"] >= threshold]
        return {
            "n_total": len(test_trades),
            "n_kept": len(kept),
            "threshold": float(threshold),
            "win_rate": float((kept["r_net"] > 0).mean()) if len(kept) else float("nan"),
            "expectancy": float(kept["r_net"].mean()) if len(kept) else float("nan"),
        }
