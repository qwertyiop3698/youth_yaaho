import pathlib

import pandas as pd
import pytest

from pipeline.layer0_data_contract import cleaner, profiler
from pipeline.layer1_features import run


@pytest.fixture
def clean_dataset_parquet(tmp_path):
    """Layer0을 직접 실행해 임시 clean_dataset.parquet을 만든다(Layer1 run 테스트용 입력)."""
    sample_path = pathlib.Path(__file__).parents[3] / "data" / "sample.csv"
    raw = pd.read_csv(sample_path)
    config = profiler.load_column_config()
    cleaned, _ = cleaner.clean_dataset(raw, config)

    path = tmp_path / "clean_dataset.parquet"
    cleaned.to_parquet(path, index=False)
    return path


def test_run_produces_featured_dataset_and_report(tmp_path, clean_dataset_parquet):
    output_dir = tmp_path / "out"
    report = run.run(clean_dataset_parquet, output_dir)

    assert (output_dir / "featured_dataset.parquet").exists()
    assert (output_dir / "feature_engineering_report.json").exists()

    featured = pd.read_parquet(output_dir / "featured_dataset.parquet")
    cleaned = pd.read_parquet(clean_dataset_parquet)

    assert len(featured) == len(cleaned)  # 행 손실 없음
    assert set(cleaned.columns).issubset(set(featured.columns))  # 원본 보존
    assert report["diagnostic_only_features"] == ["연체심각도"]


def test_run_raises_clear_error_when_input_missing(tmp_path):
    missing_input = tmp_path / "no_such_file.parquet"
    with pytest.raises(FileNotFoundError):
        run.run(missing_input, tmp_path / "out")
