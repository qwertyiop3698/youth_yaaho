import logging

import numpy as np
import pandas as pd
import pytest
from sklearn.calibration import CalibratedClassifierCV

from pipeline.layer2b_risk_model import baseline_models


def _make_separable_dataset(n=200, seed=0, positive_rate=0.5):
    rng = np.random.default_rng(seed)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    score = x1 + x2
    threshold = np.quantile(score, 1 - positive_rate)
    y = (score >= threshold).astype(int)
    df = pd.DataFrame({"feature_1": x1, "feature_2": x2})
    return df, pd.Series(y)


class TestSanitizeFeatureName:
    """2026-07-09 발견: 실제 KCB 컬럼 "파산, 개인회생 신청 여부"의 쉼표 때문에
    LightGBM이 "Do not support special JSON characters in feature name" 에러로
    학습 자체를 거부하는 버그가 있었다. 쉼표 하나만 땜질하지 않고, 한글 음절/
    영숫자/공백만 허용하는 화이트리스트 방식으로 일반화했다(당일 실데이터에 지금
    못 본 특수문자가 나와도 방어되도록)."""

    def test_comma_replaced(self):
        result = baseline_models.sanitize_feature_name("파산, 개인회생 신청 여부")
        assert "," not in result

    def test_json_special_chars_replaced(self):
        for ch in '":[]{}':
            assert ch not in baseline_models.sanitize_feature_name(f"foo{ch}bar")

    def test_parentheses_and_slash_also_replaced(self):
        """괄호/슬래시는 지금 LightGBM에서 안전하다고 확인됐지만(2026-07-09 스캔),
        화이트리스트 방식이므로 미래의 알 수 없는 특수문자 대비 차원에서 이런
        문자도 전부 치환 대상이어야 한다."""
        result = baseline_models.sanitize_feature_name("총자산평가금액(주택)")
        assert "(" not in result and ")" not in result
        result2 = baseline_models.sanitize_feature_name("차량보유(국산/수입)")
        assert "/" not in result2

    def test_korean_alphanumeric_and_space_untouched(self):
        name = "추정DTI 2년전 소득123"
        assert baseline_models.sanitize_feature_name(name) == name

    def test_build_feature_matrix_sanitizes_and_lightgbm_can_train(self):
        n = 60
        rng = np.random.default_rng(0)
        df = pd.DataFrame(
            {
                "파산, 개인회생 신청 여부": rng.choice([0, 1], n),
                "feature_1": rng.normal(size=n),
            }
        )
        y = pd.Series(rng.choice([0, 1], n))
        X, cols = baseline_models.build_feature_matrix(df)
        assert "파산, 개인회생 신청 여부" not in cols
        # 실제로 LightGBM 학습이 죽지 않아야 함(수정 전엔 여기서 LightGBMError 발생)
        baseline_models.train_lightgbm(X, y, verbosity=-1)

    def test_all_46_raw_and_derived_feature_names_sanitize_without_collision(self):
        """2026-07-09 사용자 요청: 발견된 컬럼 하나만 잡지 말고 column_groups.yaml
        46개 + Layer1 파생변수/도메인지수 20개(총 66개, 2026-07-25 "전세가변동노출"
        추가로 19->20) 전체를 스캔해서 sanitize 후에도 서로 다른 이름끼리 겹치지
        않는지, LightGBM이 실제로 학습되는지 확인."""
        import yaml

        from pipeline.layer1_features import feature_engineer as fe

        config_path = "pipeline/layer0_data_contract/column_groups.yaml"
        with open(config_path, encoding="utf-8") as f:
            cfg = yaml.safe_load(f)
        raw_cols = list(cfg["columns"].keys())
        derived_cols = (
            list(fe.FEATURE_COMPUTERS.keys())
            + ["연체심각도", "Thin Filer 보정 스코어"]
            + list(fe.DOMAIN_INDEX_DEFINITIONS.keys())
        )
        all_cols = raw_cols + derived_cols
        assert len(all_cols) == 66

        sanitized = [baseline_models.sanitize_feature_name(c) for c in all_cols]
        assert len(set(sanitized)) == len(set(all_cols))  # 충돌(다른 이름이 같은 결과로 겹침) 없어야 함

        n = 60
        rng = np.random.default_rng(0)
        X = pd.DataFrame({s: rng.normal(size=n) for s in sanitized})
        y = pd.Series(rng.choice([0, 1], n))
        baseline_models.train_lightgbm(X, y, verbosity=-1)  # 죽지 않아야 함


class TestBuildFeatureMatrix:
    def test_excludes_gated_columns_and_fills_residual_na(self):
        df = pd.DataFrame({
            "feature_1": [1.0, 2.0, np.nan],
            "대출연체건수": [0, 1, 0],  # leakage - get_model_ready_features가 제외해야 함
        })
        X, cols = baseline_models.build_feature_matrix(df)
        assert "대출연체건수" not in cols
        assert "feature_1" in cols
        assert not X["feature_1"].isna().any()  # NaN이 median으로 채워짐


class TestClassWeightBalanced:
    """2026-07-08 사용자 요청: 클래스 불균형 처리(class_weight='balanced')가 들어갔는지."""

    def test_logistic_regression_uses_balanced_class_weight_by_default(self):
        X, y = _make_separable_dataset(n=100)
        model = baseline_models.train_logistic_regression(X, y)
        assert model.get_params()["class_weight"] == "balanced"

    def test_lightgbm_uses_balanced_class_weight_by_default(self):
        X, y = _make_separable_dataset(n=100)
        model = baseline_models.train_lightgbm(X, y, verbosity=-1)
        assert model.get_params()["class_weight"] == "balanced"

    def test_explicit_class_weight_overrides_default(self):
        X, y = _make_separable_dataset(n=100)
        model = baseline_models.train_logistic_regression(X, y, class_weight=None)
        assert model.get_params()["class_weight"] is None


class TestCalibration:
    """2026-07-08 사용자 요청: risk_probability에 확률 보정이 적용됐는지."""

    def test_sufficient_sample_returns_calibrated_wrapper(self):
        X, y = _make_separable_dataset(n=200)
        model, applied = baseline_models.train_calibrated_model("logistic_regression", X, y)
        assert applied is True
        assert isinstance(model, CalibratedClassifierCV)

    def test_insufficient_class_sample_skips_calibration_but_still_predicts(self, caplog):
        X = pd.DataFrame({"feature_1": [1.0, 2.0, 3.0]})
        y = pd.Series([0, 0, 1])  # 양성 클래스 표본=1개 -> CV 폴드 구성 불가
        with caplog.at_level(logging.WARNING, logger="pipeline.layer2b_risk_model.baseline_models"):
            model, applied = baseline_models.train_calibrated_model("logistic_regression", X, y)
        assert applied is False
        assert not isinstance(model, CalibratedClassifierCV)
        assert any("보정" in r.message for r in caplog.records)
        # 보정 안 된 모델도 predict_proba는 정상 동작해야 함(호출부가 신경 쓸 필요 없게)
        proba = model.predict_proba(X)
        assert proba.shape == (3, 2)


class TestEvaluateBinaryClassifier:
    def test_single_class_subset_returns_none_metrics_without_crashing(self):
        X, y = _make_separable_dataset(n=50)
        model = baseline_models.train_logistic_regression(X, y)
        single_class_idx = y[y == 0].index  # 평가 대상이 한 클래스만 포함하는 상황(fold 쏠림 등)
        result = baseline_models.evaluate_binary_classifier(
            model, X.loc[single_class_idx], y.loc[single_class_idx]
        )
        assert result["auc_roc"] is None
        assert result["pr_auc"] is None
        assert result["calibration"] is None

    def test_reports_baseline_pr_auc_equal_to_positive_rate(self):
        X, y = _make_separable_dataset(n=300, positive_rate=0.2)
        model = baseline_models.train_logistic_regression(X, y)
        result = baseline_models.evaluate_binary_classifier(model, X, y)
        assert result["baseline_pr_auc"] == pytest.approx(float(y.mean()), abs=1e-9)

    def test_pr_auc_lift_logged_and_varies_with_imbalance(self, caplog):
        """2026-07-08 사용자 요청: 불균형 정도에 따라 PR-AUC가 어떻게 변하는지 로그로 남기기.
        양성비율이 다른 세 데이터셋(50%/10%/2%)에서 baseline_pr_auc가 실제로 그 비율을
        따라가는지, 그리고 lift 로그가 남는지 확인한다."""
        records = {}
        for rate in (0.5, 0.1, 0.02):
            X, y = _make_separable_dataset(n=1000, seed=1, positive_rate=rate)
            model = baseline_models.train_logistic_regression(X, y)
            with caplog.at_level(logging.INFO, logger="pipeline.layer2b_risk_model.baseline_models"):
                result = baseline_models.evaluate_binary_classifier(model, X, y)
            records[rate] = result
            assert result["baseline_pr_auc"] == pytest.approx(rate, abs=0.02)

        assert any("lift" in r.message for r in caplog.records)
        # 불균형이 심할수록(양성비율이 낮을수록) baseline PR-AUC 자체는 낮아져야 함
        assert records[0.5]["baseline_pr_auc"] > records[0.1]["baseline_pr_auc"] > records[0.02]["baseline_pr_auc"]


class TestTrainAndCompareModels:
    def test_separable_data_yields_high_auc(self):
        X, y = _make_separable_dataset(n=200)
        result = baseline_models.train_and_compare_models(X, y, min_train_sample=30)
        assert result["skipped"] is False
        assert result["logistic_regression"]["metrics"]["auc_roc"] > 0.8
        assert result["lightgbm"]["metrics"]["auc_roc"] > 0.6

    def test_skips_gracefully_when_event_is_single_class(self):
        X, _ = _make_separable_dataset(n=10)
        y = pd.Series([0] * 10)
        result = baseline_models.train_and_compare_models(X, y)
        assert result["skipped"] is True
        assert result["reason"] == "event 라벨 단일 클래스"

    def test_small_sample_logs_warning_but_still_runs(self, caplog):
        X, y = _make_separable_dataset(n=10)
        with caplog.at_level(logging.WARNING, logger="pipeline.layer2b_risk_model.baseline_models"):
            result = baseline_models.train_and_compare_models(X, y, min_train_sample=30)
        assert any("표본 부족" in r.message for r in caplog.records)
        assert result["skipped"] is False  # event가 2클래스면 표본이 적어도 학습은 진행

    def test_uses_holdout_split_for_sufficient_sample(self):
        X, y = _make_separable_dataset(n=200)
        result = baseline_models.train_and_compare_models(X, y)
        assert result["holdout_used"] is True

    def test_falls_back_to_in_sample_for_tiny_sample(self):
        X, y = _make_separable_dataset(n=10)
        result = baseline_models.train_and_compare_models(X, y)
        assert result["holdout_used"] is False

    def test_tiny_sample_defaults_to_logistic_regression_not_in_sample_pr_auc(self):
        """2026-07-08 사용자 지적: held-out이 없을 때 in-sample PR-AUC로 비교하면
        LightGBM(표현력이 큼)이 과대적합 덕에 부풀려진 점수로 선택될 구조적 위험이
        있다. holdout_used=False면 비교 없이 로지스틱을 기본 선택해야 한다."""
        X, y = _make_separable_dataset(n=10)
        result = baseline_models.train_and_compare_models(X, y)
        assert result["holdout_used"] is False
        assert result["best_model_name"] == "logistic_regression"
        assert "과대적합" in result["selection_reason"]
        assert "PR-AUC" not in result["selection_reason"]  # in-sample PR-AUC 비교를 하지 않았다는 증거

    def test_selects_best_model_by_pr_auc_and_records_reason(self):
        X, y = _make_separable_dataset(n=200)
        result = baseline_models.train_and_compare_models(X, y)
        assert result["holdout_used"] is True
        assert result["best_model_name"] in ("logistic_regression", "lightgbm")
        assert "held-out PR-AUC" in result["selection_reason"]
        assert result["deployed_model"] is not None
        assert result["raw_lightgbm_for_shap"] is not None

    def test_deployed_model_predicts_proba_for_full_dataset(self):
        X, y = _make_separable_dataset(n=200)
        result = baseline_models.train_and_compare_models(X, y)
        proba = result["deployed_model"].predict_proba(X)
        assert proba.shape == (len(X), 2)

    def test_calibration_applied_flags_present_for_both_models(self):
        X, y = _make_separable_dataset(n=200)
        result = baseline_models.train_and_compare_models(X, y)
        assert set(result["calibration_applied"].keys()) == {"logistic_regression", "lightgbm"}
        assert result["calibration_applied"]["logistic_regression"] is True
        assert result["calibration_applied"]["lightgbm"] is True
