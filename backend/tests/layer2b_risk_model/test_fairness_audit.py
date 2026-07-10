import numpy as np
import pandas as pd

from pipeline.layer2b_risk_model import baseline_models, fairness_audit


def _make_dataset(n=200, seed=0):
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = (x1 + x2 > 0).astype(int)
    subgroup = pd.Series(rng.choice(["male", "female"], size=n))
    return pd.DataFrame({"feature_1": x1, "feature_2": x2}), pd.Series(y), subgroup


class TestAuditBySubgroup:
    def test_computes_metrics_for_sufficient_subgroups(self):
        X, y, subgroup = _make_dataset()
        model = baseline_models.train_logistic_regression(X, y)
        result = fairness_audit.audit_by_subgroup(model, X, y, subgroup, min_subgroup_sample=20)

        assert "male" in result and "female" in result
        for key in ("male", "female"):
            assert result[key]["skipped"] is False
            assert result[key]["auc_roc"] is not None
            assert result[key]["pr_auc"] is not None

    def test_skips_small_subgroup(self):
        X, y, _ = _make_dataset(n=50)
        model = baseline_models.train_logistic_regression(X, y)
        subgroup = pd.Series(["small"] * 5 + ["large"] * 45)

        result = fairness_audit.audit_by_subgroup(model, X, y, subgroup, min_subgroup_sample=20)

        assert result["small"]["skipped"] is True
        assert result["small"]["reason"] == "표본 부족"
        assert result["large"]["skipped"] is False
