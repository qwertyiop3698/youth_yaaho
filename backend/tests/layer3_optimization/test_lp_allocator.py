import os
import subprocess
import sys
import time

import numpy as np
import pandas as pd
import pytest

from pipeline.layer3_optimization import lp_allocator


def _simple_catalog():
    return {
        "policies": {
            "정책A": {
                "target_domains": {"도메인1": 1.0},
                "effectiveness_prior": 0.5,
                "unit_cost": 100,
                "budget_cap": 250,
                "eligibility": {"age_range": {"min": 19, "max": 34, "confidence": "verified"}},
            },
            "정책B": {
                "target_domains": {"도메인2": 1.0},
                "effectiveness_prior": 0.4,
                "unit_cost": 100,
                "budget_cap": 1000,
                "eligibility": {
                    "requires_no_home_ownership": {
                        "column": "자가거주여부",
                        "expected_value": 0,
                        "confidence": "assumed_unresolved_codebook",
                    }
                },
            },
        },
        "defaults": {"max_policy_per_person": 1},
    }


def _make_people(n=10, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame(
        {
            "risk_probability": rng.uniform(0.3, 0.9, n),
            "도메인1": rng.normal(0, 1, n),
            "도메인2": rng.normal(0, 1, n),
            "연령대": rng.choice([20, 25, 30, 40], n),
            "자가거주여부": rng.choice([0, 1], n),
        }
    )


class TestComputeRelevanceScore:
    def test_zero_z_score_is_neutral_half(self):
        df = pd.DataFrame({"도메인1": [0.0]})
        result = lp_allocator.compute_relevance_score(df, {"도메인1": 1.0})
        assert result.iloc[0] == pytest.approx(0.5)

    def test_higher_domain_value_yields_higher_relevance(self):
        df = pd.DataFrame({"도메인1": [-3.0, 0.0, 3.0]})
        result = lp_allocator.compute_relevance_score(df, {"도메인1": 1.0})
        assert result.iloc[0] < result.iloc[1] < result.iloc[2]

    def test_missing_domain_column_defaults_to_neutral(self):
        df = pd.DataFrame({"다른컬럼": [1, 2, 3]})
        result = lp_allocator.compute_relevance_score(df, {"없는도메인": 1.0})
        assert (result == 0.5).all()

    def test_weighted_average_of_multiple_domains(self):
        df = pd.DataFrame({"도메인1": [0.0], "도메인2": [0.0]})
        result = lp_allocator.compute_relevance_score(df, {"도메인1": 0.5, "도메인2": 0.5})
        assert result.iloc[0] == pytest.approx(0.5)


class TestEvaluateEligibility:
    def test_age_in_range_is_eligible_and_verified(self):
        df = pd.DataFrame({"연령대": [25]})
        cfg = {"eligibility": {"age_range": {"min": 19, "max": 34, "confidence": "verified"}}}
        result = lp_allocator.evaluate_policy_eligibility(df, "정책A", cfg)
        assert result.loc[0, "eligible"] == True  # noqa: E712
        assert result.loc[0, "confidence"] == "verified"

    def test_age_out_of_range_is_ineligible(self):
        df = pd.DataFrame({"연령대": [50]})
        cfg = {"eligibility": {"age_range": {"min": 19, "max": 34, "confidence": "verified"}}}
        result = lp_allocator.evaluate_policy_eligibility(df, "정책A", cfg)
        assert result.loc[0, "eligible"] == False  # noqa: E712

    def test_unresolved_codebook_rule_defaults_to_eligible_with_downgraded_confidence(self):
        df = pd.DataFrame({"자가거주여부": [3]})  # 코드북 불확실한 임의 값
        cfg = {
            "eligibility": {
                "requires_no_home_ownership": {
                    "column": "자가거주여부",
                    "expected_value": 0,
                    "confidence": "assumed_unresolved_codebook",
                }
            }
        }
        result = lp_allocator.evaluate_policy_eligibility(df, "정책B", cfg)
        assert result.loc[0, "eligible"] == True  # noqa: E712
        assert result.loc[0, "confidence"] == "assumed_unresolved_codebook"

    def test_excluded_value_rule_is_eligible_and_verified_when_value_differs(self):
        """2026-07-25: 자가거주여부는 "1이면 본인소유주택거주"만 명세로 확인됐다
        (0/3 등 나머지 코드의 세부 의미는 여전히 미확정). excluded_value=1은 "1이
        아니면 무주택 조건 충족"만 검증하므로, 값이 1이 아니면(0이든 3이든) 나머지
        코드값 의미를 몰라도 verified로 처리할 수 있어야 한다."""
        df = pd.DataFrame({"자가거주여부": [3]})  # 세부 의미는 몰라도 1이 아님은 확실
        cfg = {
            "eligibility": {
                "requires_no_home_ownership": {
                    "column": "자가거주여부",
                    "excluded_value": 1,
                    "confidence": "verified",
                }
            }
        }
        result = lp_allocator.evaluate_policy_eligibility(df, "정책B", cfg)
        assert result.loc[0, "eligible"] == True  # noqa: E712
        assert result.loc[0, "confidence"] == "verified"

    def test_excluded_value_rule_is_ineligible_when_value_matches(self):
        df = pd.DataFrame({"자가거주여부": [1]})  # 확실히 본인소유주택거주
        cfg = {
            "eligibility": {
                "requires_no_home_ownership": {
                    "column": "자가거주여부",
                    "excluded_value": 1,
                    "confidence": "verified",
                }
            }
        }
        result = lp_allocator.evaluate_policy_eligibility(df, "정책B", cfg)
        assert result.loc[0, "eligible"] == False  # noqa: E712
        assert result.loc[0, "confidence"] == "verified"

    def test_verified_rule_with_missing_value_falls_back_to_eligible_and_unresolved(self):
        df = pd.DataFrame({"연령대": [None]})
        cfg = {"eligibility": {"age_range": {"min": 19, "max": 34, "confidence": "verified"}}}
        result = lp_allocator.evaluate_policy_eligibility(df, "정책A", cfg)
        assert result.loc[0, "eligible"] == True  # noqa: E712
        assert result.loc[0, "confidence"] == "assumed_unresolved_codebook"

    def test_no_eligibility_rules_means_everyone_eligible_and_verified(self):
        df = pd.DataFrame({"연령대": [25, 50]})
        cfg = {"eligibility": {}}
        result = lp_allocator.evaluate_policy_eligibility(df, "정책X", cfg)
        assert result["eligible"].all()
        assert (result["confidence"] == "verified").all()


class TestComputeDeltaRisk:
    def test_formula_matches_risk_times_relevance_times_effectiveness(self):
        df = pd.DataFrame({"risk_probability": [0.8], "도메인1": [0.0], "연령대": [25]})
        catalog = _simple_catalog()
        delta_risk, _ = lp_allocator.compute_delta_risk(df, catalog)
        # 도메인1=0 -> sigmoid(0)=0.5 -> relevance=0.5, effectiveness_prior=0.5
        expected = 0.8 * 0.5 * 0.5
        assert delta_risk[(0, "정책A")] == pytest.approx(expected)

    def test_effectiveness_override_replaces_prior(self):
        df = pd.DataFrame({"risk_probability": [0.8], "도메인1": [0.0], "연령대": [25]})
        catalog = _simple_catalog()
        delta_risk, _ = lp_allocator.compute_delta_risk(df, catalog, effectiveness_override={"정책A": 0.9})
        assert delta_risk[(0, "정책A")] == pytest.approx(0.8 * 0.5 * 0.9)

    def test_missing_risk_column_raises(self):
        df = pd.DataFrame({"도메인1": [0.0]})
        with pytest.raises(ValueError):
            lp_allocator.compute_delta_risk(df, _simple_catalog())


class TestBuildAndSolveLp:
    def test_budget_constraint_never_exceeded(self):
        df = _make_people(n=20)
        catalog = _simple_catalog()
        assignment_df, report = lp_allocator.build_and_solve_lp(df, catalog, max_policy_per_person=2)

        for policy, cfg in catalog["policies"].items():
            spent = (assignment_df["policy"] == policy).sum() * cfg["unit_cost"]
            assert spent <= cfg["budget_cap"]

    def test_max_policy_per_person_respected(self):
        df = _make_people(n=20)
        catalog = _simple_catalog()
        assignment_df, _ = lp_allocator.build_and_solve_lp(df, catalog, max_policy_per_person=1)
        counts = assignment_df.groupby("person_id").size()
        assert (counts <= 1).all()

    def test_ineligible_person_never_assigned(self):
        df = pd.DataFrame(
            {
                "risk_probability": [0.9, 0.9],
                "도메인1": [2.0, 2.0],
                "도메인2": [2.0, 2.0],
                "연령대": [50, 25],  # 첫 사람은 정책A(19~34) 자격 미충족
                "자가거주여부": [0, 0],
            }
        )
        catalog = _simple_catalog()
        assignment_df, _ = lp_allocator.build_and_solve_lp(df, catalog, max_policy_per_person=2)
        person0_policies = set(assignment_df[assignment_df["person_id"] == 0]["policy"])
        assert "정책A" not in person0_policies

    def test_assignment_includes_eligibility_confidence_column(self):
        df = _make_people(n=10)
        catalog = _simple_catalog()
        assignment_df, _ = lp_allocator.build_and_solve_lp(df, catalog)
        assert "eligibility_confidence" in assignment_df.columns
        assert set(assignment_df["eligibility_confidence"].unique()) <= {"verified", "assumed_unresolved_codebook"}

    def test_skips_gracefully_when_risk_column_missing(self):
        df = pd.DataFrame({"도메인1": [0.0, 0.0]})
        assignment_df, report = lp_allocator.build_and_solve_lp(df, _simple_catalog())
        assert report["skipped"] is True
        assert len(assignment_df) == 0

    def test_solves_to_optimal_status(self):
        df = _make_people(n=10)
        _, report = lp_allocator.build_and_solve_lp(df, _simple_catalog())
        assert report["status"] == "Optimal"

    def test_report_flags_true_optimal_solution(self):
        # 2026-07-10 발견: budget_cap이 빡빡하면 CBC가 시간제한에 걸려 증명된
        # 최적해가 아니라 "그 시점까지 찾은 최선의 실행가능해"로 끝날 수 있다.
        # solver_status/is_optimal 필드로 둘을 구분해야 나중에 배정표가 진짜
        # 최적인지 시간 다 돼서 멈춘 건지 알 수 있다.
        df = _make_people(n=10)
        _, report = lp_allocator.build_and_solve_lp(df, _simple_catalog())
        assert report["solver_status"] == "Optimal Solution Found"
        assert report["is_optimal"] is True

    def test_normal_solve_does_not_trigger_watchdog(self):
        """2026-07-25: 워치독 추가가 정상 케이스(작은 문제, 빨리 풀림)를 건드리지
        않아야 한다."""
        df = _make_people(n=10)
        _, report = lp_allocator.build_and_solve_lp(df, _simple_catalog())
        assert report["solver_watchdog_killed"] is False


class _FakeProb:
    """실제 pulp.LpProblem 대신 solve() 소요시간을 통제하기 위한 대역."""

    def __init__(self, delay: float):
        self.delay = delay
        self.solved = False

    def solve(self, solver):  # noqa: ARG002 - 워치독은 solver 인자를 그대로 전달만 함
        time.sleep(self.delay)
        self.solved = True


class TestSolveWithHardTimeout:
    """2026-07-25 실측: 자격조건이 촘촘해진 뒤 100,816명 규모에서 PuLP의 timeLimit이
    지켜지지 않고(CBC가 체크포인트에 도달 못 함) 21분 넘게 하드행되는 것을 발견 -
    PuLP 자체엔 파이썬 쪽 강제종료가 없어서(COIN_CMD.solve_CBC가 timeout 없는
    cbc.wait()) 프로세스 트리를 직접 감시하는 워치독을 추가했다."""

    def test_fast_solve_returns_not_timed_out(self):
        prob = _FakeProb(delay=0.05)
        timed_out = lp_allocator._solve_with_hard_timeout(
            prob, solver=None, timeout_seconds=1.0, kill_grace_seconds=0.5
        )
        assert timed_out is False
        assert prob.solved is True

    def test_slow_solve_returns_timed_out_without_waiting_full_delay(self):
        prob = _FakeProb(delay=2.0)
        start = time.monotonic()
        timed_out = lp_allocator._solve_with_hard_timeout(
            prob, solver=None, timeout_seconds=0.2, kill_grace_seconds=0.1
        )
        elapsed = time.monotonic() - start
        assert timed_out is True
        # 워치독이 실제로 개입해 hard_deadline(0.3초) 근방에서 리턴해야 한다
        # (delay=2.0초를 다 기다리면 실패로 간주).
        assert elapsed < 1.0


class TestKillProcessTreeByName:
    """실제 자식 프로세스를 하나 띄워서 이름 매칭 킬 로직을 검증한다."""

    def _spawn_sleeper(self) -> subprocess.Popen:
        return subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    def test_kills_matching_child_process(self):
        proc = self._spawn_sleeper()
        try:
            time.sleep(0.3)  # 자식 프로세스가 psutil에 잡힐 시간을 준다
            exe_name = os.path.basename(sys.executable).lower()
            killed = lp_allocator._kill_process_tree_by_name(os.getpid(), {exe_name})
            assert proc.pid in killed
            assert proc.wait(timeout=5) != 0  # 강제종료됐으므로 정상 종료(0)가 아님
        finally:
            if proc.poll() is None:
                proc.kill()

    def test_does_not_kill_non_matching_process(self):
        proc = self._spawn_sleeper()
        try:
            time.sleep(0.3)
            killed = lp_allocator._kill_process_tree_by_name(os.getpid(), {"definitely_not_a_real_process.exe"})
            assert proc.pid not in killed
            assert proc.poll() is None  # 여전히 살아있어야 함
        finally:
            proc.kill()
            proc.wait(timeout=5)
