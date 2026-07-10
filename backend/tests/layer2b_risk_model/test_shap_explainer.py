import numpy as np
import pandas as pd

from pipeline.layer2b_risk_model import baseline_models, shap_explainer


def _make_dataset(n=100, seed=0):
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = (x1 + x2 > 0).astype(int)
    return pd.DataFrame({"feature_1": x1, "feature_2": x2}), pd.Series(y)


class TestTopKShapFeatures:
    def test_returns_k_entries_with_expected_schema(self):
        X, y = _make_dataset()
        model = baseline_models.train_lightgbm(X, y, verbosity=-1)
        result = shap_explainer.top_k_shap_features(model, X, k=2)

        assert len(result) == len(X)
        first = result.iloc[0]
        assert len(first) == 2
        for item in first:
            assert set(item.keys()) == {"feature", "impact"}
            assert item["feature"] in X.columns
            assert isinstance(item["impact"], float)

    def test_empty_input_returns_empty_series(self):
        X, y = _make_dataset()
        model = baseline_models.train_lightgbm(X, y, verbosity=-1)
        result = shap_explainer.top_k_shap_features(model, X.iloc[0:0], k=3)
        assert len(result) == 0
