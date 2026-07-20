import numpy as np
import pandas as pd
import pytest

from pipeline.layer2a_clustering import risk_trajectory_simulator as rts


def _profiles_1d(positions: dict[str, float]) -> pd.DataFrame:
    """1차원 도메인지수 공간에 클러스터 중심을 배치(거리 비교를 쉽게 하기 위함)."""
    return pd.DataFrame({"주거비압박지수": positions}).loc[list(positions.keys())]


class TestComputeClusterAvgRisk:
    def test_weighted_average_matches_manual_calculation(self):
        membership = pd.DataFrame(
            {"cluster_0": [1.0, 0.0, 0.5], "cluster_1": [0.0, 1.0, 0.5]}, index=["p1", "p2", "p3"]
        )
        risk = pd.Series([0.2, 0.8, 0.5], index=["p1", "p2", "p3"])
        result = rts.compute_cluster_avg_risk(membership, risk)
        # cluster_0: (1.0*0.2 + 0.5*0.5) / (1.0 + 0.5) = 0.45/1.5 = 0.3
        assert result["cluster_0"] == pytest.approx(0.3)
        # cluster_1: (1.0*0.8 + 0.5*0.5) / (1.0 + 0.5) = 1.05/1.5 = 0.7
        assert result["cluster_1"] == pytest.approx(0.7)


class TestComputePopulationInitialDistribution:
    def test_normalizes_to_sum_one(self):
        membership = pd.DataFrame(
            {"cluster_0": [1.0, 0.0, 0.5], "cluster_1": [0.0, 1.0, 0.5]}, index=["p1", "p2", "p3"]
        )
        result = rts.compute_population_initial_distribution(membership)
        assert result.sum() == pytest.approx(1.0)
        assert result["cluster_0"] == pytest.approx(1.5 / 3.0)
        assert result["cluster_1"] == pytest.approx(1.5 / 3.0)


class TestBuildTransitionMatrix:
    def test_rows_sum_to_one(self):
        profiles = _profiles_1d({"cluster_0": 0.0, "cluster_1": 1.0, "cluster_2": 5.0})
        avg_risk = pd.Series({"cluster_0": 0.2, "cluster_1": 0.5, "cluster_2": 0.8})
        matrix = rts.build_transition_matrix(profiles, avg_risk, risk_bias=0.7, min_self_transition=0.4)
        row_sums = matrix.sum(axis=1)
        assert row_sums.to_numpy() == pytest.approx(np.ones(3))

    def test_self_transition_respects_minimum(self):
        profiles = _profiles_1d({"cluster_0": 0.0, "cluster_1": 1.0, "cluster_2": 5.0})
        avg_risk = pd.Series({"cluster_0": 0.2, "cluster_1": 0.5, "cluster_2": 0.8})
        matrix = rts.build_transition_matrix(profiles, avg_risk, min_self_transition=0.6)
        for cluster in matrix.index:
            assert matrix.loc[cluster, cluster] == pytest.approx(0.6)

    def test_closer_cluster_gets_higher_transition_weight(self):
        # risk_bias=0이라 순수 거리(affinity)만 반영 - cluster_0은 cluster_1(거리 1)이
        # cluster_2(거리 5)보다 훨씬 가까우므로 전이확률도 더 커야 한다.
        profiles = _profiles_1d({"cluster_0": 0.0, "cluster_1": 1.0, "cluster_2": 5.0})
        avg_risk = pd.Series({"cluster_0": 0.5, "cluster_1": 0.5, "cluster_2": 0.5})
        matrix = rts.build_transition_matrix(profiles, avg_risk, risk_bias=0.0, min_self_transition=0.5)
        assert matrix.loc["cluster_0", "cluster_1"] > matrix.loc["cluster_0", "cluster_2"]

    def test_positive_risk_bias_favors_higher_risk_neighbor(self):
        # cluster_0에서 cluster_1(위험 낮음)과 cluster_2(위험 높음)가 거리상 대칭이면,
        # risk_bias>0일 때 cluster_2 쪽 전이확률이 더 커야 한다(무개입: 위험 심화 방향).
        profiles = _profiles_1d({"cluster_0": 0.0, "cluster_1": -2.0, "cluster_2": 2.0})
        avg_risk = pd.Series({"cluster_0": 0.5, "cluster_1": 0.2, "cluster_2": 0.8})
        matrix = rts.build_transition_matrix(profiles, avg_risk, risk_bias=1.0, min_self_transition=0.3)
        assert matrix.loc["cluster_0", "cluster_2"] > matrix.loc["cluster_0", "cluster_1"]

    def test_single_cluster_is_fully_self_transitioning(self):
        profiles = _profiles_1d({"cluster_0": 0.0})
        avg_risk = pd.Series({"cluster_0": 0.5})
        matrix = rts.build_transition_matrix(profiles, avg_risk)
        assert matrix.loc["cluster_0", "cluster_0"] == pytest.approx(1.0)


class TestSimulateTrajectory:
    def test_matches_manual_two_cluster_calculation(self):
        # 2-클러스터, 전이행렬을 직접 지정해 matrix power와 비교
        transition = pd.DataFrame([[0.9, 0.1], [0.2, 0.8]], index=["cluster_0", "cluster_1"], columns=["cluster_0", "cluster_1"])
        avg_risk = pd.Series({"cluster_0": 0.1, "cluster_1": 0.9})
        initial = pd.Series({"cluster_0": 1.0, "cluster_1": 0.0})

        result = rts.simulate_trajectory(initial, transition, avg_risk, n_steps=2)

        # step 0: 그대로 [1, 0]
        assert result.loc[0, "cluster_0"] == pytest.approx(1.0)
        assert result.loc[0, "expected_avg_risk"] == pytest.approx(0.1)
        # step 1: [1,0] @ T = [0.9, 0.1]
        assert result.loc[1, "cluster_0"] == pytest.approx(0.9)
        assert result.loc[1, "cluster_1"] == pytest.approx(0.1)
        assert result.loc[1, "expected_avg_risk"] == pytest.approx(0.9 * 0.1 + 0.1 * 0.9)
        # step 2: [0.9,0.1] @ T
        expected_step2 = np.array([0.9, 0.1]) @ transition.to_numpy()
        assert result.loc[2, "cluster_0"] == pytest.approx(expected_step2[0])
        assert result.loc[2, "cluster_1"] == pytest.approx(expected_step2[1])

    def test_initial_distribution_is_normalized(self):
        transition = pd.DataFrame([[1.0, 0.0], [0.0, 1.0]], index=["cluster_0", "cluster_1"], columns=["cluster_0", "cluster_1"])
        avg_risk = pd.Series({"cluster_0": 0.0, "cluster_1": 1.0})
        initial = pd.Series({"cluster_0": 2.0, "cluster_1": 2.0})  # 합이 4 -> 0.5/0.5로 정규화돼야 함
        result = rts.simulate_trajectory(initial, transition, avg_risk, n_steps=0)
        assert result.loc[0, "cluster_0"] == pytest.approx(0.5)
        assert result.loc[0, "cluster_1"] == pytest.approx(0.5)


class TestSimulateNoInterventionVsIntervention:
    def test_intervention_reduces_expected_avg_risk_after_n_steps(self):
        profiles = _profiles_1d({"cluster_0": 0.0, "cluster_1": -2.0, "cluster_2": 2.0})
        avg_risk = pd.Series({"cluster_0": 0.5, "cluster_1": 0.2, "cluster_2": 0.8})
        initial = pd.Series({"cluster_0": 1.0, "cluster_1": 0.0, "cluster_2": 0.0})

        result = rts.simulate_no_intervention_vs_intervention(
            profiles,
            avg_risk,
            initial,
            intervention_effectiveness=0.8,
            n_steps=6,
            min_self_transition=0.3,
        )

        assert result["is_simulation"] is True
        assert "실제" in result["simulation_disclaimer"]

        no_intervention_final = result["no_intervention"][-1]["expected_avg_risk"]
        intervention_final = result["intervention"][-1]["expected_avg_risk"]
        assert intervention_final < no_intervention_final

    def test_zero_effectiveness_still_produces_a_valid_matrix(self):
        profiles = _profiles_1d({"cluster_0": 0.0, "cluster_1": 1.0})
        avg_risk = pd.Series({"cluster_0": 0.4, "cluster_1": 0.6})
        initial = pd.Series({"cluster_0": 1.0, "cluster_1": 0.0})
        result = rts.simulate_no_intervention_vs_intervention(
            profiles, avg_risk, initial, intervention_effectiveness=0.0, n_steps=3
        )
        assert len(result["intervention"]) == 4
        assert len(result["no_intervention"]) == 4
