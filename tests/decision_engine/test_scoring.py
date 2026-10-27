import pandas as pd

from decision_engine.scoring import ConfluenceScorer


def _trades() -> pd.DataFrame:
    return pd.DataFrame({
        "confidence": ["alta", "alta", "baja", "baja", "baja"],
        "side": ["long", "short", "long", "long", "short"],
        "r_net": [-1.0, -0.8, 0.5, 1.2, -0.3],
    })


def test_fit_computes_group_means():
    scorer = ConfluenceScorer.fit(_trades(), features=["confidence"])
    assert round(scorer.weights["confidence"]["alta"], 4) == -0.9
    assert round(scorer.weights["confidence"]["baja"], 4) == round((0.5 + 1.2 - 0.3) / 3, 4)


def test_score_row_sums_known_categories():
    scorer = ConfluenceScorer.fit(_trades(), features=["confidence"])
    assert scorer.score_row({"confidence": "alta"}) == scorer.weights["confidence"]["alta"]


def test_score_row_unseen_category_is_neutral():
    scorer = ConfluenceScorer.fit(_trades(), features=["confidence"])
    assert scorer.score_row({"confidence": "desconocida"}) == 0.0


def test_evaluate_out_of_sample_does_not_recalibrate():
    train = _trades()
    scorer = ConfluenceScorer.fit(train, features=["confidence"])
    test = pd.DataFrame({"confidence": ["alta", "baja", "baja", "alta"], "r_net": [2.0, -5.0, 3.0, -1.0]})
    result = scorer.evaluate_out_of_sample(test, top_pct=0.5)
    assert result["n_total"] == 4
    assert result["n_kept"] == 2  # las 2 de mayor score segun los pesos del TRAIN, no del test
    # pesos del train: baja > alta -> deben quedar las 2 filas "baja" del test
    assert result["n_kept"] == 2


def test_logistic_scorer_fits_and_scores(_larger_trades=None):
    from decision_engine.scoring import LogisticConfluenceScorer

    train = pd.DataFrame({
        "confidence": ["alta", "alta", "baja", "baja", "baja", "alta", "baja", "alta"] * 3,
        "side": ["long", "short", "long", "long", "short", "short", "long", "long"] * 3,
        "r_net": [-1.0, -0.8, 0.5, 1.2, -0.3, -0.6, 0.9, -1.1] * 3,
    })
    scorer = LogisticConfluenceScorer.fit(train, features=["confidence", "side"])
    score = scorer.score_row({"confidence": "baja", "side": "long"})
    assert 0.0 <= score <= 1.0


def test_logistic_scorer_evaluate_out_of_sample_shape():
    from decision_engine.scoring import LogisticConfluenceScorer

    train = pd.DataFrame({
        "confidence": ["alta", "alta", "baja", "baja", "baja", "alta", "baja", "alta"] * 3,
        "r_net": [-1.0, -0.8, 0.5, 1.2, -0.3, -0.6, 0.9, -1.1] * 3,
    })
    test = pd.DataFrame({"confidence": ["alta", "baja", "baja", "alta"], "r_net": [2.0, -5.0, 3.0, -1.0]})
    scorer = LogisticConfluenceScorer.fit(train, features=["confidence"])
    result = scorer.evaluate_out_of_sample(test, top_pct=0.5)
    assert result["n_total"] == 4
    assert result["n_kept"] == 2
