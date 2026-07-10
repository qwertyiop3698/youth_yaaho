import pathlib

import numpy as np
import pandas as pd
import pytest

from pipeline.layer0_data_contract import cleaner, profiler
from pipeline.layer1_features import feature_engineer as fe
from pipeline.layer2a_clustering import gmm_trainer, run


def _synthetic_featured_dataset(n_per_cluster=60, seed=0):
    rng = np.random.default_rng(seed)
    centers = [(-3, -3, 0, 0, 0), (3, 3, 0, 0, 0), (0, 0, 3, 3, 3)]
    rows = []
    for c in centers:
        for _ in range(n_per_cluster):
            rows.append([c[i] + rng.normal(0, 0.3) for i in range(5)])
    return pd.DataFrame(rows, columns=gmm_trainer.DOMAIN_INDEX_COLUMNS)


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

        assert report["model_trained"] is False
        assert not (output_dir / "cluster_model.pkl").exists()
        assert not (output_dir / "cluster_membership.parquet").exists()
        assert (output_dir / "cluster_report.json").exists()


class TestRunTrainsModelWithSufficientSample:
    def test_synthetic_well_separated_clusters_produce_artifacts(self, tmp_path):
        df = _synthetic_featured_dataset()
        input_path = tmp_path / "featured_dataset.parquet"
        df.to_parquet(input_path, index=False)
        output_dir = tmp_path / "out"

        report = run.run(input_path, output_dir)

        assert report["model_trained"] is True
        assert (output_dir / "cluster_model.pkl").exists()
        assert (output_dir / "cluster_membership.parquet").exists()
        assert (output_dir / "cluster_report.json").exists()

        membership = pd.read_parquet(output_dir / "cluster_membership.parquet")
        assert len(membership) == len(df)
        assert "suggested_labels" in report


def test_run_raises_clear_error_when_input_missing(tmp_path):
    with pytest.raises(FileNotFoundError):
        run.run(tmp_path / "no_such_file.parquet", tmp_path / "out")
