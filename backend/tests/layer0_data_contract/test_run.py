import pandas as pd

from pipeline.layer0_data_contract import cleaner, profiler, run


def test_run_produces_expected_artifacts(tmp_path):
    result = run.run(run.DEFAULT_INPUT, tmp_path)

    assert (tmp_path / "clean_dataset.parquet").exists()
    assert (tmp_path / "profiling_report.json").exists()
    assert (tmp_path / "profiling_report.md").exists()
    assert (tmp_path / "cleaning_report.json").exists()

    cleaned = pd.read_parquet(tmp_path / "clean_dataset.parquet")
    original = pd.read_csv(run.DEFAULT_INPUT)
    assert len(cleaned) == len(original)  # 행 손실 없음
    assert len(cleaned.columns) > len(original.columns)  # 플래그 컬럼 추가됨

    config = result["profiling_report"]  # profile_dataset 결과 재사용 확인용
    assert config["row_count"] == len(original)


def test_run_output_still_contains_quasi_identifier_join_keys(tmp_path):
    """조인/spatial CV/행정 집계용으로는 clean_dataset에 시군구코드가 남아있어야 한다."""
    run.run(run.DEFAULT_INPUT, tmp_path)
    cleaned = pd.read_parquet(tmp_path / "clean_dataset.parquet")

    original_columns = pd.read_csv(run.DEFAULT_INPUT).columns
    config = profiler.load_column_config()
    for col in cleaner.get_quasi_identifier_columns(config):
        if col in original_columns:
            assert col in cleaned.columns
