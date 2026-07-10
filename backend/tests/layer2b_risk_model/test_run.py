import pathlib

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.base import BaseEstimator
from sklearn.calibration import CalibratedClassifierCV

from pipeline.layer0_data_contract import cleaner, profiler
from pipeline.layer1_features import feature_engineer as fe
from pipeline.layer2b_risk_model import run


def _synthetic_featured_dataset(n=300, n_groups=10, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for i in range(n):
        rows.append(
            {
                "대출연체건수": int(rng.random() < 0.15),
                "카드연체건수": 0,
                "추정DTI": rng.uniform(0, 1),
                "소득증감률": rng.normal(0, 0.2),
                "신용평점": rng.uniform(0, 1000),
                "성별": rng.choice([1, 2]),
                "연령대": rng.choice([20, 25, 30, 35]),
                "거주지 시군구 코드": f"sigungu_{i % n_groups}",
            }
        )
    return pd.DataFrame(rows)


class TestRunSkipsGracefullyOnTinySample:
    def test_real_sample_csv_skips_without_crashing(self, tmp_path):
        sample_path = pathlib.Path(__file__).parents[3] / "data" / "sample.csv"
        raw = pd.read_csv(sample_path)
        config = profiler.load_column_config()
        cleaned, _ = cleaner.clean_dataset(raw, config)
        featured, _ = fe.engineer_features(cleaned, config)

        input_path = tmp_path / "featured_dataset.parquet"
        featured.to_parquet(input_path, index=False)
        output_dir = tmp_path / "out"

        report = run.run(input_path, output_dir)

        assert report["training"]["skipped"] is True
        assert not (output_dir / "risk_model.pkl").exists()
        assert not (output_dir / "risk_scores.parquet").exists()
        assert (output_dir / "risk_model_report.json").exists()


class TestRunTrainsModelWithSufficientSample:
    def test_synthetic_dataset_produces_all_artifacts(self, tmp_path):
        df = _synthetic_featured_dataset()
        input_path = tmp_path / "featured_dataset.parquet"
        df.to_parquet(input_path, index=False)
        output_dir = tmp_path / "out"

        report = run.run(input_path, output_dir)

        assert report["training"]["skipped"] is False
        assert (output_dir / "risk_model.pkl").exists()
        assert (output_dir / "risk_scores.parquet").exists()
        assert (output_dir / "risk_model_report.json").exists()

        risk_scores = pd.read_parquet(output_dir / "risk_scores.parquet")
        assert "event_probability" in risk_scores.columns
        assert "shap_top3" in risk_scores.columns
        assert (risk_scores["event_probability"].between(0, 1)).all()
        assert report["logistic_regression_metrics"]["auc_roc"] is not None
        assert report["lightgbm_metrics"]["auc_roc"] is not None
        assert "성별" in report["fairness_audit"]
        assert "연령대" in report["fairness_audit"]

        # 2026-07-08 보강: 모델 선택 기준 + 확률 보정 + risk_model.pkl 번들 구조 확인
        assert report["best_model_name"] in ("logistic_regression", "lightgbm")
        assert "PR-AUC" in report["selection_reason"]
        assert report["calibration_applied"]["logistic_regression"] is True
        assert report["calibration_applied"]["lightgbm"] is True
        assert report["deployed_model_calibrated"] is True

        bundle = joblib.load(output_dir / "risk_model.pkl")
        assert set(bundle.keys()) == {"model", "model_type", "shap_model"}
        assert bundle["model_type"] == report["best_model_name"]
        assert isinstance(bundle["model"], (CalibratedClassifierCV, BaseEstimator))
        # SHAP 전용 모델은 항상 원본(미보정) LightGBM이어야 함(CalibratedClassifierCV가 아님)
        assert not isinstance(bundle["shap_model"], CalibratedClassifierCV)


def test_run_raises_clear_error_when_input_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        run.run(tmp_path / "no_such_file.parquet", tmp_path / "out")
