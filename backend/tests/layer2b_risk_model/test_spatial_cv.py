import numpy as np
import pandas as pd
import pytest

from pipeline.layer0_data_contract import profiler
from pipeline.layer2b_risk_model import baseline_models, spatial_cv


@pytest.fixture(scope="module")
def config():
    return profiler.load_column_config()


class TestResolveSpatialGroupColumn:
    def test_prefers_dong_when_present(self, config):
        df = pd.DataFrame({"거주지행정동": ["A", "B"], "거주지 시군구 코드": [1, 2]})
        assert spatial_cv.resolve_spatial_group_column(df, config) == "거주지행정동"

    def test_falls_back_to_sigungu_when_dong_absent(self, config):
        df = pd.DataFrame({"거주지 시군구 코드": [1, 2]})
        assert spatial_cv.resolve_spatial_group_column(df, config) == "거주지 시군구 코드"

    def test_returns_none_when_neither_present(self, config):
        df = pd.DataFrame({"성별": [1, 2]})
        assert spatial_cv.resolve_spatial_group_column(df, config) is None


def _make_grouped_dataset(n_groups=10, per_group=10, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for g in range(n_groups):
        for _ in range(per_group):
            x1, x2 = rng.normal(), rng.normal()
            rows.append({
                "feature_1": x1,
                "feature_2": x2,
                "거주지 시군구 코드": f"sigungu_{g}",
                "event": int(x1 + x2 > 0),
            })
    return pd.DataFrame(rows)


class TestSpatialCrossValidate:
    def test_skips_when_insufficient_groups_or_sample(self, config):
        df = pd.DataFrame({"feature_1": [1, 2, 3], "거주지 시군구 코드": ["a", "b", "c"]})
        y = pd.Series([0, 1, 0])
        result = spatial_cv.spatial_cross_validate(
            df,
            df[["feature_1"]],
            y,
            train_fn=baseline_models.train_logistic_regression,
            eval_fn=baseline_models.evaluate_binary_classifier,
            layer0_config=config,
        )
        assert result["skipped"] is True

    def test_returns_skipped_when_no_group_column_available(self, config):
        df = pd.DataFrame({"feature_1": [1, 2, 3]})
        y = pd.Series([0, 1, 0])
        result = spatial_cv.spatial_cross_validate(
            df,
            df[["feature_1"]],
            y,
            train_fn=baseline_models.train_logistic_regression,
            eval_fn=baseline_models.evaluate_binary_classifier,
            layer0_config=config,
        )
        assert result["skipped"] is True
        assert result["group_column"] is None

    def test_runs_folds_with_sufficient_groups_and_sample(self, config):
        df = _make_grouped_dataset()
        X = df[["feature_1", "feature_2"]]
        y = df["event"]
        result = spatial_cv.spatial_cross_validate(
            df,
            X,
            y,
            train_fn=baseline_models.train_logistic_regression,
            eval_fn=baseline_models.evaluate_binary_classifier,
            n_splits=5,
            layer0_config=config,
            min_groups=5,
            min_sample=30,
        )
        assert result["skipped"] is False
        assert result["group_column"] == "거주지 시군구 코드"
        assert len(result["folds"]) > 0
        for fold in result["folds"]:
            assert "metrics" in fold
