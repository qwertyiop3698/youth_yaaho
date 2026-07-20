import numpy as np
import pandas as pd
import pytest

from pipeline.layer2b_risk_model import fairness_correction


def _biased_dataset(n_per_group=100, seed=0):
    """male은 점수가 라벨과 잘 분리되고, female은 양성이어도 점수가 체계적으로
    낮게 나오도록(under-scoring) 만들어 baseline_threshold=0.6에서 그룹 간 TPR
    격차가 크게 벌어지게 한다 - 실제 공정성 감사에서 발견될 법한 패턴을 재현."""
    rng = np.random.default_rng(seed)

    male_y = rng.choice([0, 1], size=n_per_group, p=[0.6, 0.4])
    male_proba = np.where(male_y == 1, rng.uniform(0.65, 0.95, n_per_group), rng.uniform(0.05, 0.35, n_per_group))

    female_y = rng.choice([0, 1], size=n_per_group, p=[0.6, 0.4])
    # 양성이어도 점수가 baseline_threshold(0.6) 아래로 나오도록 낮게 분포시킨다.
    female_proba = np.where(
        female_y == 1, rng.uniform(0.35, 0.55, n_per_group), rng.uniform(0.05, 0.3, n_per_group)
    )

    y_true = pd.Series(np.concatenate([male_y, female_y]))
    y_proba = pd.Series(np.concatenate([male_proba, female_proba]))
    group = pd.Series(["male"] * n_per_group + ["female"] * n_per_group)
    return y_true, y_proba, group


class TestComputeEqualizedOddsThresholds:
    def test_reduces_tpr_gap_between_groups(self):
        y_true, y_proba, group = _biased_dataset()
        correction = fairness_correction.compute_equalized_odds_thresholds(
            y_true, y_proba, group, baseline_threshold=0.6, min_subgroup_sample=20
        )
        assert correction["skipped"] is False

        evaluation = fairness_correction.evaluate_correction(
            y_true, y_proba, group, correction["thresholds"], correction["baseline_threshold"]
        )
        assert evaluation["before_tpr_gap"] is not None
        assert evaluation["after_tpr_gap"] is not None
        # 보정 전 격차가 실제로 커야 이 테스트가 의미가 있다(구성이 의도대로 됐는지).
        assert evaluation["before_tpr_gap"] > 0.3
        assert evaluation["after_tpr_gap"] < evaluation["before_tpr_gap"]
        assert evaluation["improved"] is True

    def test_thresholds_are_within_probability_range(self):
        y_true, y_proba, group = _biased_dataset()
        correction = fairness_correction.compute_equalized_odds_thresholds(y_true, y_proba, group)
        for threshold in correction["thresholds"].values():
            assert 0.0 <= threshold <= 1.0

    def test_small_subgroup_keeps_baseline_threshold(self):
        y_true, y_proba, group = _biased_dataset(n_per_group=50)
        small_group = group.copy()
        small_group.iloc[:5] = "tiny"  # 5명뿐인 그룹 추가(min_subgroup_sample=20 미달)

        correction = fairness_correction.compute_equalized_odds_thresholds(
            y_true, y_proba, small_group, baseline_threshold=0.6, min_subgroup_sample=20
        )
        assert correction["thresholds"]["tiny"] == pytest.approx(0.6)
        assert correction["details"]["tiny"]["skipped"] is True
        assert correction["details"]["tiny"]["reason"] == "표본 부족"

    def test_skipped_when_no_positive_cases(self):
        y_true = pd.Series([0] * 20)
        y_proba = pd.Series(np.linspace(0, 1, 20))
        group = pd.Series(["a"] * 10 + ["b"] * 10)
        correction = fairness_correction.compute_equalized_odds_thresholds(y_true, y_proba, group)
        assert correction["skipped"] is True


class TestEvaluateCorrection:
    def test_gap_is_none_when_fewer_than_two_groups_have_positives(self):
        y_true = pd.Series([1, 1, 0, 0])
        y_proba = pd.Series([0.9, 0.8, 0.2, 0.1])
        group = pd.Series(["only_group"] * 4)
        result = fairness_correction.evaluate_correction(y_true, y_proba, group, {"only_group": 0.5}, 0.5)
        assert result["before_tpr_gap"] is None
        assert result["after_tpr_gap"] is None
