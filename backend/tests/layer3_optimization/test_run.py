import numpy as np
import pandas as pd
import pytest
import yaml

from pipeline.layer3_optimization import run


def _write_synthetic_inputs(tmp_path, n=30, seed=0):
    rng = np.random.default_rng(seed)
    featured_df = pd.DataFrame(
        {
            "주거비압박지수": rng.normal(0, 1, n),
            "부채상환위험지수": rng.normal(0, 1, n),
            "소득변동성지수": rng.normal(0, 1, n),
            "소비압박지수": rng.normal(0, 1, n),
            "신용취약지수": rng.normal(0, 1, n),
            "연령대": rng.choice([20, 25, 30, 35], n),
            "자가거주여부": rng.choice([0, 1], n),
        }
    )
    risk_scores = pd.DataFrame({"event_probability": rng.uniform(0.2, 0.9, n)})

    featured_path = tmp_path / "featured_dataset.parquet"
    risk_scores_path = tmp_path / "risk_scores.parquet"
    featured_df.to_parquet(featured_path, index=True)
    risk_scores.to_parquet(risk_scores_path, index=True)
    return featured_path, risk_scores_path


class TestRunEndToEnd:
    def test_produces_all_artifacts(self, tmp_path):
        featured_path, risk_scores_path = _write_synthetic_inputs(tmp_path)
        output_dir = tmp_path / "out"

        report = run.run(featured_path, risk_scores_path, run.DEFAULT_POLICY_CATALOG, output_dir)

        assert (output_dir / "assignment_results.parquet").exists()
        assert (output_dir / "budget_sensitivity.parquet").exists()
        assert (output_dir / "regret_curve.parquet").exists()
        assert (output_dir / "regret_segment_summary.parquet").exists()
        assert (output_dir / "optimization_report.json").exists()

        assignment_df = pd.read_parquet(output_dir / "assignment_results.parquet")
        assert "eligibility_confidence" in assignment_df.columns

        assert report["bandit"]["is_simulation"] is True
        assert "simulation_disclaimer" in report["bandit"]

        # 2026-07-09 보강: 구간별 regret + prior-true 격차가 리포트에 포함되는지 확인
        assert len(report["bandit"]["segment_regret"]) == 3
        gap_records = report["bandit"]["effectiveness_prior_vs_true_gap"]
        assert len(gap_records) == 6
        gaps = [r["gap"] for r in gap_records]
        assert any(g > 0 for g in gaps)
        assert any(g < 0 for g in gaps)

    def test_raises_clear_error_when_featured_dataset_missing(self, tmp_path):
        _, risk_scores_path = _write_synthetic_inputs(tmp_path)
        with pytest.raises(FileNotFoundError):
            run.run(tmp_path / "no_such_featured.parquet", risk_scores_path, run.DEFAULT_POLICY_CATALOG, tmp_path / "out")

    def test_raises_clear_error_when_risk_scores_missing(self, tmp_path):
        featured_path, _ = _write_synthetic_inputs(tmp_path)
        with pytest.raises(FileNotFoundError):
            run.run(featured_path, tmp_path / "no_such_risk_scores.parquet", run.DEFAULT_POLICY_CATALOG, tmp_path / "out")


def test_load_policy_catalog_reads_six_policies():
    catalog = run.load_policy_catalog()
    assert len(catalog["policies"]) == 6
    assert "defaults" in catalog
