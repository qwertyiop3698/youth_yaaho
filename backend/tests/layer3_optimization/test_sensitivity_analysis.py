import numpy as np
import pandas as pd
import pytest

from pipeline.layer3_optimization import sensitivity_analysis


def _catalog(budget_a=100, budget_b=100):
    return {
        "policies": {
            "정책A": {
                "target_domains": {"도메인1": 1.0},
                "effectiveness_prior": 0.5,
                "unit_cost": 100,
                "budget_cap": budget_a,
                "eligibility": {},
            },
            "정책B": {
                "target_domains": {"도메인2": 1.0},
                "effectiveness_prior": 0.4,
                "unit_cost": 100,
                "budget_cap": budget_b,
                "eligibility": {"age_range": {"min": 19, "max": 34, "confidence": "verified"}},
            },
        },
        "defaults": {"max_policy_per_person": 2},
    }


def _make_people(n=20, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "risk_probability": rng.uniform(0.3, 0.9, n),
            "도메인1": rng.normal(0, 1, n),
            "도메인2": rng.normal(0, 1, n),
            "연령대": rng.choice([20, 25, 30], n),  # 전원 정책B 자격 충족(verified)
        }
    )


class TestComputeCoverageRate:
    def test_overall_and_verified_only_differ_when_confidence_mixed(self):
        assignment_df = pd.DataFrame(
            {
                "person_id": [0, 1, 2],
                "policy": ["정책A", "정책A", "정책B"],
                "eligibility_confidence": ["assumed_unresolved_codebook", "assumed_unresolved_codebook", "verified"],
            }
        )
        coverage = sensitivity_analysis.compute_coverage_rate(assignment_df, total_persons=3)
        assert coverage["overall"] == pytest.approx(3 / 3)
        assert coverage["verified_only"] == pytest.approx(1 / 3)

    def test_zero_persons_returns_none(self):
        coverage = sensitivity_analysis.compute_coverage_rate(pd.DataFrame(), total_persons=0)
        assert coverage["overall"] is None
        assert coverage["verified_only"] is None

    def test_empty_assignment_returns_zero_coverage(self):
        coverage = sensitivity_analysis.compute_coverage_rate(
            pd.DataFrame(columns=["person_id", "policy", "eligibility_confidence"]), total_persons=5
        )
        assert coverage["overall"] == 0.0
        assert coverage["verified_only"] == 0.0


class TestRunBudgetSensitivity:
    def test_coverage_is_non_decreasing_as_budget_increases(self):
        df = _make_people(n=30)
        catalog = _catalog(budget_a=50, budget_b=50)  # 예산을 빠듯하게 잡아 배율 효과가 보이게
        result = sensitivity_analysis.run_budget_sensitivity(
            df, catalog, multipliers=(0.5, 1.0, 1.5), max_policy_per_person=2
        )
        assert list(result["budget_multiplier"]) == [0.5, 1.0, 1.5]
        coverages = result["coverage_overall"].tolist()
        assert coverages == sorted(coverages)  # 예산이 늘수록 커버리지가 줄어들 수 없음

    def test_verified_only_never_exceeds_overall(self):
        df = _make_people(n=30)
        catalog = _catalog(budget_a=50, budget_b=50)
        result = sensitivity_analysis.run_budget_sensitivity(df, catalog, multipliers=(0.5, 1.0, 1.5))
        assert (result["coverage_verified_only"] <= result["coverage_overall"] + 1e-9).all()

    def test_reports_skipped_when_no_valid_risk_scores(self):
        df = pd.DataFrame({"도메인1": [0.0, 0.0]})
        result = sensitivity_analysis.run_budget_sensitivity(df, _catalog(), multipliers=(1.0,))
        assert bool(result["skipped"].iloc[0]) is True


def _tight_catalog(unit_cost=10, budget_a=50, budget_b=50):
    # unit_cost를 budget_cap보다 훨씬 작게 잡아 bump가 정수 슬롯 수를 실제로
    # 늘리도록 한다(unit_cost=budget_cap에 가까우면 10~50% 정도의 bump로는
    # floor(budget/unit_cost)가 그대로라 marginal_gain이 항상 0으로 나올 수 있다).
    return {
        "policies": {
            "정책A": {
                "target_domains": {"도메인1": 1.0},
                "effectiveness_prior": 0.5,
                "unit_cost": unit_cost,
                "budget_cap": budget_a,
                "eligibility": {},
            },
            "정책B": {
                "target_domains": {"도메인2": 1.0},
                "effectiveness_prior": 0.4,
                "unit_cost": unit_cost,
                "budget_cap": budget_b,
                "eligibility": {"age_range": {"min": 19, "max": 34, "confidence": "verified"}},
            },
        },
        "defaults": {"max_policy_per_person": 2},
    }


class TestRunPerPolicyMarginalAnalysis:
    def test_bumping_one_policy_does_not_mutate_input_catalog(self):
        df = _make_people(n=30)
        catalog = _tight_catalog()
        sensitivity_analysis.run_per_policy_marginal_analysis(df, catalog, bump=0.5, max_policy_per_person=2)
        assert catalog["policies"]["정책A"]["budget_cap"] == 50
        assert catalog["policies"]["정책B"]["budget_cap"] == 50

    def test_bumping_a_tight_budget_increases_its_own_coverage(self):
        df = _make_people(n=30)
        catalog = _tight_catalog()  # 5 slots per policy(budget 50 / unit_cost 10)
        result = sensitivity_analysis.run_per_policy_marginal_analysis(
            df, catalog, bump=0.5, max_policy_per_person=2
        )
        assert set(result["policy"]) == {"정책A", "정책B"}
        valid = result["marginal_gain_per_10pct"].dropna()
        assert not valid.empty
        # 슬롯이 빠듯한 상황에서 그 정책 예산만 늘렸으므로 커버리지가 줄어들 수는 없다
        assert (valid >= -1e-9).all()
        assert (result["bumped_coverage"] >= result["baseline_coverage"] - 1e-9).all()

    def test_result_sorted_descending_by_marginal_gain(self):
        df = _make_people(n=30)
        catalog = _tight_catalog()
        result = sensitivity_analysis.run_per_policy_marginal_analysis(df, catalog, bump=0.5)
        gains = result["marginal_gain_per_10pct"].dropna().tolist()
        assert gains == sorted(gains, reverse=True)

    def test_reports_skipped_when_no_valid_risk_scores(self):
        df = pd.DataFrame({"도메인1": [0.0, 0.0]})
        result = sensitivity_analysis.run_per_policy_marginal_analysis(df, _catalog())
        assert bool(result["skipped"].iloc[0]) is True
        assert result["marginal_gain_per_10pct"].isna().all()


class TestMarginalGainPer10PctBudget:
    def test_linear_coverage_yields_expected_marginal_gain(self):
        df = pd.DataFrame({"budget_multiplier": [0.5, 1.0, 1.5], "coverage_overall": [0.2, 0.4, 0.6]})
        gain = sensitivity_analysis.marginal_gain_per_10pct_budget(df)
        # budget 1.0 증가에 coverage 0.4 증가 -> 10%(0.1) 증가에 0.04
        assert gain == pytest.approx(0.04, abs=1e-9)

    def test_insufficient_data_returns_none(self):
        df = pd.DataFrame({"budget_multiplier": [1.0], "coverage_overall": [0.5]})
        assert sensitivity_analysis.marginal_gain_per_10pct_budget(df) is None
