import numpy as np
import yaml

from pipeline.layer3_optimization import run, synthetic_reward


class TestSimulateReward:
    def test_success_rate_roughly_matches_true_effectiveness(self):
        rng = np.random.default_rng(0)
        true_effectiveness = {"정책A": 0.8}
        n = 5000
        successes = sum(synthetic_reward.simulate_reward("정책A", true_effectiveness, rng) for _ in range(n))
        rate = successes / n
        assert abs(rate - 0.8) < 0.03

    def test_unknown_policy_defaults_to_half(self):
        rng = np.random.default_rng(0)
        n = 5000
        successes = sum(synthetic_reward.simulate_reward("없는정책", {}, rng) for _ in range(n))
        rate = successes / n
        assert abs(rate - 0.5) < 0.03

    def test_uses_default_true_effectiveness_when_not_provided(self):
        rng = np.random.default_rng(0)
        n = 3000
        policy = "청년월세지원"
        successes = sum(synthetic_reward.simulate_reward(policy, rng=rng) for _ in range(n))
        rate = successes / n
        assert abs(rate - synthetic_reward.DEFAULT_TRUE_EFFECTIVENESS[policy]) < 0.03


class TestComputePriorVsTrueGap:
    """2026-07-09 사용자 요청: prior와 true_effectiveness 격차가 데모에서 설득력
    있을 만큼(방향이 섞이고, 크기도 충분히) 벌어져 있는지 확인."""

    def test_gap_directions_are_mixed_not_uniform(self):
        catalog = run.load_policy_catalog()
        gap_df = synthetic_reward.compute_prior_vs_true_gap(catalog)
        assert (gap_df["gap"] > 0).any()  # 과소평가(상향 조정) 사례가 존재
        assert (gap_df["gap"] < 0).any()  # 과대평가(하향 조정) 사례가 존재

    def test_gap_magnitude_is_large_enough_to_be_demo_convincing(self):
        catalog = run.load_policy_catalog()
        gap_df = synthetic_reward.compute_prior_vs_true_gap(catalog)
        assert gap_df["gap"].abs().mean() >= 0.15  # 평균 절대격차가 충분히 커야 함
        assert (gap_df["gap"].abs() >= 0.1).all()  # 격차가 0에 가까운(설득력 없는) 정책이 없어야 함

    def test_gap_dataframe_has_expected_columns(self):
        catalog = run.load_policy_catalog()
        gap_df = synthetic_reward.compute_prior_vs_true_gap(catalog)
        assert set(gap_df.columns) == {"policy", "effectiveness_prior", "true_effectiveness", "gap", "direction"}
        assert len(gap_df) == 6
