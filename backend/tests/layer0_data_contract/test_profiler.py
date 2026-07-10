import pathlib

import pandas as pd
import pytest

from pipeline.layer0_data_contract import profiler


@pytest.fixture(scope="module")
def config():
    return profiler.load_column_config()


class TestZeroValueSemantics:
    """docs/02: 같은 0도 컬럼마다 의미가 다르다 - 그룹 판단표대로 동작하는지 확인."""

    def test_loan_delinquency_zero_is_normal_not_flagged(self, config):
        df = pd.DataFrame({"대출연체건수": [0, 0, 0, 0, 0]})
        result = profiler.profile_column(
            df["대출연체건수"], config["columns"]["대출연체건수"], config["defaults"]
        )
        assert result["zero_pct"] == 1.0
        assert result["needs_human_review"] is False

    def test_ambiguous_income_zero_is_flagged_for_review(self, config):
        df = pd.DataFrame({"추정월소득": [0, 0, 300, 250, 180]})
        result = profiler.profile_column(
            df["추정월소득"], config["columns"]["추정월소득"], config["defaults"]
        )
        assert result["needs_human_review"] is True
        assert any("불확실" in r for r in result["review_reasons"])

    def test_proof_income_zero_is_normal_not_flagged(self, config):
        df = pd.DataFrame({"증빙연소득": [0, 0, 0, 500, 600]})
        result = profiler.profile_column(
            df["증빙연소득"], config["columns"]["증빙연소득"], config["defaults"]
        )
        assert result["zero_pct"] == 0.6
        assert result["needs_human_review"] is False


class TestSentinelDetection:
    """docs/02: -99999999 등 sentinel 값 자동 탐지."""

    def test_known_sentinel_value_detected_via_exact_match(self, config):
        col = "2년내 현거주지평균전세거래가"
        df = pd.DataFrame({col: [-99999999, -99999999, -99999999, -99999999, 10512]})
        result = profiler.profile_column(df[col], config["columns"][col], config["defaults"])
        assert result["known_sentinel"]["hits"] == {-99999999: 4}
        assert result["needs_human_review"] is True

    def test_statistical_outlier_skipped_when_sample_too_small(self, config):
        col = "총자산평가금액(주택)"
        df = pd.DataFrame({col: [59780, 168000, 147680, 62670, 300000]})
        defaults = config["defaults"]
        result = profiler.detect_statistical_outliers(
            df[col], defaults["sentinel_iqr_multiplier"], defaults["min_sample_for_iqr"]
        )
        assert result["checked"] is False

    def test_statistical_outlier_detected_with_enough_sample(self):
        normal_values = [100, 105, 98, 102, 101, 99, 103, 97, 104, 100,
                          102, 99, 101, 98, 103, 100, 97, 102, 101, 99]
        series = pd.Series(normal_values + [50_000_000])  # n=21, 극단값 1개 추가
        result = profiler.detect_statistical_outliers(series, iqr_multiplier=1000, min_sample=20)
        assert result["checked"] is True
        assert 50_000_000 in result["candidates"]


class TestUnknownCategory:
    def test_unknown_code_outside_codebook_detected(self, config):
        df = pd.DataFrame({"성별": [1, 2, 1, 9, 2]})
        result = profiler.detect_unknown_categories(df["성별"], config["columns"]["성별"]["codebook"])
        assert result["checked"] is True
        assert result["unknown_count"] == 1

    def test_no_codebook_configured_skips_check(self, config):
        df = pd.DataFrame({"직업군": [420, 910, 420]})
        result = profiler.detect_unknown_categories(df["직업군"], config["columns"]["직업군"]["codebook"])
        assert result["checked"] is False


class TestDatasetLevelProfiling:
    def test_missing_and_unmapped_columns_do_not_crash(self, config):
        """실데이터 컬럼 구성이 명세와 달라도(컬럼 누락/신규 컬럼) 죽지 않아야 한다."""
        df = pd.DataFrame({"성별": [1, 2], "미확인컬럼": ["a", "b"]})
        report = profiler.profile_dataset(df, config)
        assert "거주지행정동" in report["missing_from_data"]
        assert "미확인컬럼" in report["unmapped_in_data"]
        assert "성별" in report["columns"]

    def test_real_sample_csv_profiles_without_error(self):
        sample_path = pathlib.Path(__file__).parents[3] / "data" / "sample.csv"
        df = pd.read_csv(sample_path)
        cfg = profiler.load_column_config()
        report = profiler.profile_dataset(df, cfg)

        assert report["row_count"] == 5
        # docs/02가 명시한 4개 미제공 컬럼(직업군상세/거주지행정동/근무지행정동/추정가구원수)
        assert set(report["missing_from_data"]) == {
            "직업군상세", "거주지행정동", "근무지행정동", "추정가구원수",
        }
        assert report["unmapped_in_data"] == []
        # docs/02가 확인한 sentinel 컬럼들이 검토 필요 목록에 잡히는지 확인
        assert "2년내 현거주지평균전세거래가" in report["needs_human_review"]
        assert "2년내 현거주지평균실거래가" in report["needs_human_review"]

    def test_generate_profiling_report_writes_json_and_md(self, tmp_path):
        df = pd.DataFrame({"성별": [1, 2, None]})
        cfg = profiler.load_column_config()
        json_path = tmp_path / "profiling_report.json"
        md_path = tmp_path / "profiling_report.md"

        report = profiler.generate_profiling_report(df, cfg, json_path, md_path)

        assert json_path.exists()
        assert md_path.exists()
        assert "성별" in report["columns"]
        assert "컬럼별 요약" in md_path.read_text(encoding="utf-8")
