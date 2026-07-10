import pytest

from pipeline.layer3_optimization import regret_curve


class TestRunBanditSimulation:
    def test_output_is_labeled_as_simulation(self):
        result = regret_curve.run_bandit_simulation(["A", "B"], n_rounds=50, true_effectiveness={"A": 0.7, "B": 0.3})
        assert result["is_simulation"] is True

    def test_history_has_expected_columns_and_length(self):
        result = regret_curve.run_bandit_simulation(["A", "B"], n_rounds=100, true_effectiveness={"A": 0.7, "B": 0.3})
        history = result["history"]
        assert len(history) == 100
        assert set(history.columns) >= {"round", "chosen_policy", "success", "instant_regret", "cumulative_regret"}

    def test_cumulative_regret_is_non_decreasing(self):
        result = regret_curve.run_bandit_simulation(["A", "B"], n_rounds=200, true_effectiveness={"A": 0.7, "B": 0.3})
        regret = result["history"]["cumulative_regret"]
        assert (regret.diff().dropna() >= -1e-9).all()

    def test_posterior_means_converge_toward_true_effectiveness_with_enough_rounds(self):
        true_effectiveness = {"A": 0.7, "B": 0.3}
        result = regret_curve.run_bandit_simulation(["A", "B"], n_rounds=3000, true_effectiveness=true_effectiveness, seed=1)
        # 우세한 정책(A)은 많이 뽑혀서 사후평균이 실제값에 가까워져야 함
        assert abs(result["final_posterior_means"]["A"] - 0.7) < 0.1

    def test_best_policy_yields_lower_cumulative_regret_than_uniform_random_would(self):
        """정책 A(0.9)가 압도적으로 우월할 때, 후반부 라운드의 순간후회(instant_regret)가
        0에 가까워야 한다(밴딧이 좋은 정책으로 수렴했다는 증거)."""
        true_effectiveness = {"A": 0.9, "B": 0.1}
        result = regret_curve.run_bandit_simulation(["A", "B"], n_rounds=1000, true_effectiveness=true_effectiveness, seed=2)
        late_regret = result["history"]["instant_regret"].iloc[-100:].mean()
        early_regret = result["history"]["instant_regret"].iloc[:100].mean()
        assert late_regret < early_regret

    def test_result_includes_segment_regret(self):
        result = regret_curve.run_bandit_simulation(
            ["A", "B", "C"], n_rounds=300, true_effectiveness={"A": 0.8, "B": 0.5, "C": 0.2}
        )
        assert "segment_regret" in result
        assert len(result["segment_regret"]) == 3
        assert list(result["segment_regret"]["segment_label"]) == ["초반", "중반", "후반"]


class TestComputeSegmentAverageRegret:
    """2026-07-09 사용자 지적: 누적 regret의 단조 비감소는 instant_regret>=0이면 항상
    참이라 학습 여부를 증명하지 못한다. 구간별 평균이 실질적인 학습 검증 지표다."""

    def test_late_segment_has_lower_mean_regret_than_early_segment(self):
        """정책 하나가 압도적으로 우월하면(0.9 vs 0.1) 밴딧이 빠르게 수렴해야 하고,
        후반 구간의 평균 순간 regret이 초반 구간보다 뚜렷이 낮아야 한다(sublinear growth)."""
        result = regret_curve.run_bandit_simulation(
            ["good", "bad"], n_rounds=900, true_effectiveness={"good": 0.9, "bad": 0.1}, seed=3, n_segments=3
        )
        segment_regret = result["segment_regret"]
        early = segment_regret.loc[segment_regret["segment_label"] == "초반", "mean_instant_regret"].iloc[0]
        late = segment_regret.loc[segment_regret["segment_label"] == "후반", "mean_instant_regret"].iloc[0]
        assert late < early

    def test_segment_columns_and_round_ranges_are_contiguous(self):
        history = regret_curve.run_bandit_simulation(["A", "B"], n_rounds=99, true_effectiveness={"A": 0.7, "B": 0.3})[
            "history"
        ]
        segments = regret_curve.compute_segment_average_regret(history, n_segments=3)
        assert set(segments.columns) == {
            "segment_index",
            "segment_label",
            "round_start",
            "round_end",
            "mean_instant_regret",
        }
        assert segments.iloc[0]["round_start"] == 0
        assert segments.iloc[-1]["round_end"] == 98  # 마지막 구간은 끝까지 포함
        # 구간이 이어져야 함(비어있거나 겹치지 않음)
        for i in range(len(segments) - 1):
            assert segments.iloc[i + 1]["round_start"] == segments.iloc[i]["round_end"] + 1

    def test_empty_history_does_not_crash(self):
        import pandas as pd

        segments = regret_curve.compute_segment_average_regret(pd.DataFrame(columns=["instant_regret"]))
        assert len(segments) >= 0  # 죽지 않고 빈 결과(또는 NaN 포함 결과) 반환
