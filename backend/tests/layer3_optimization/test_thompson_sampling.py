import numpy as np
import pytest

from pipeline.layer3_optimization.thompson_sampling import ThompsonSamplingBandit


class TestInitialState:
    def test_default_prior_is_uniform_beta_1_1(self):
        bandit = ThompsonSamplingBandit(["A", "B"])
        assert bandit.alpha == {"A": 1.0, "B": 1.0}
        assert bandit.beta == {"A": 1.0, "B": 1.0}
        assert bandit.posterior_mean("A") == pytest.approx(0.5)


class TestUpdate:
    def test_success_increments_alpha(self):
        bandit = ThompsonSamplingBandit(["A"])
        bandit.update("A", success=True)
        assert bandit.alpha["A"] == 2.0
        assert bandit.beta["A"] == 1.0

    def test_failure_increments_beta(self):
        bandit = ThompsonSamplingBandit(["A"])
        bandit.update("A", success=False)
        assert bandit.alpha["A"] == 1.0
        assert bandit.beta["A"] == 2.0

    def test_posterior_mean_reflects_observed_success_rate_after_many_updates(self):
        bandit = ThompsonSamplingBandit(["A"])
        for _ in range(97):
            bandit.update("A", success=True)
        for _ in range(3):
            bandit.update("A", success=False)
        # 100번 중 97번 성공 -> alpha=98, beta=4 -> posterior_mean ≈ 0.96
        assert bandit.posterior_mean("A") == pytest.approx(98 / 102, abs=1e-9)


class TestSelectPolicy:
    def test_select_policy_prefers_policy_with_much_higher_posterior(self):
        bandit = ThompsonSamplingBandit(["good", "bad"])
        for _ in range(200):
            bandit.update("good", success=True)
        for _ in range(200):
            bandit.update("bad", success=False)
        rng = np.random.default_rng(0)
        choices = [bandit.select_policy(rng) for _ in range(50)]
        assert choices.count("good") > choices.count("bad")

    def test_state_reports_alpha_beta_for_all_policies(self):
        bandit = ThompsonSamplingBandit(["A", "B"])
        bandit.update("A", success=True)
        state = bandit.state()
        assert state["A"] == {"alpha": 2.0, "beta": 1.0}
        assert state["B"] == {"alpha": 1.0, "beta": 1.0}
