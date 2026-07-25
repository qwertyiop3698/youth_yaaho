import pandas as pd
import pytest

from pipeline.layer0_data_contract import external_loader


def _sample_raw_df() -> pd.DataFrame:
    """실제 부산_인구현황 CSV 구조를 축소 재현(2개 시군구, 소계행 포함)."""
    return pd.DataFrame({
        "시군구코드": [26110, 26110, 26110, 26140, 26140],
        "시군구명": ["중구", "중구", "중구", "서구", "서구"],
        "행정동코드": [2611000000, 2611051000, 2611052000, 2614000000, 2614051000],
        "행정동명": ["소계", "중앙동", "동광동", "소계", "동대신동"],
        "거주자인구수": [5000, 3000, 2000, 8000, 8000],
        "세대수": [3000, 1800, 1200, 4500, 4500],
        "세대당인구": [1.67, 1.67, 1.67, 1.78, 1.78],
        "남자인구수": [2400, 1440, 960, 3900, 3900],
        "여자인구수": [2600, 1560, 1040, 4100, 4100],
        "남여비율": [0.92, 0.92, 0.92, 0.95, 0.95],
    })


class TestLoadPopulationCsv:
    def test_missing_required_column_raises_clear_error(self, tmp_path):
        bad_csv = tmp_path / "bad.csv"
        pd.DataFrame({"시군구코드": [26110]}).to_csv(bad_csv, index=False, encoding="utf-8")

        with pytest.raises(ValueError, match="필요한 컬럼이 없습니다"):
            external_loader.load_population_csv(bad_csv)

    def test_loads_valid_csv(self, tmp_path):
        csv_path = tmp_path / "population.csv"
        _sample_raw_df().to_csv(csv_path, index=False, encoding="utf-8")

        df = external_loader.load_population_csv(csv_path)
        assert len(df) == 5


class TestBuildSigunguPopulationReference:
    def test_excludes_subtotal_rows_and_sums_detail_rows(self):
        ref, report = external_loader.build_sigungu_population_reference(_sample_raw_df())

        ref_indexed = ref.set_index("시군구코드")["population_reference"]
        assert ref_indexed[26110] == 5000  # 3000 + 2000 (소계 5000행은 집계에서 제외, 결과는 같음)
        assert ref_indexed[26140] == 8000
        assert report["subtotal_rows_excluded"] == 2
        assert report["detail_rows_used"] == 3
        assert report["n_sigungu"] == 2

    def test_age_filter_and_time_dimension_are_reported_as_unavailable(self):
        """연령대/시간대 컬럼이 원본에 없다는 사실을 리포트가 감추지 않아야 한다
        (미션 지시: 불가능하면 전체 생활인구 사용하되 그 사실을 리포트에 명시)."""
        _, report = external_loader.build_sigungu_population_reference(_sample_raw_df())

        assert report["age_filter_applied"] is False
        assert "연령대" in report["age_filter_reason"]
        assert report["time_dimension_available"] is False

    def test_subtotal_mismatch_is_flagged_not_silently_trusted(self):
        df = _sample_raw_df()
        df.loc[df["행정동명"] == "소계", "거주자인구수"] = [9999, 8000]  # 26110 소계를 일부러 틀리게

        _, report = external_loader.build_sigungu_population_reference(df)

        assert "26110" in report["subtotal_mismatch_sigungu_codes"]
        assert "26140" not in report["subtotal_mismatch_sigungu_codes"]


class TestBuildDongPopulationReference:
    def test_excludes_subtotal_rows_only(self):
        dong_ref = external_loader.build_dong_population_reference(_sample_raw_df())

        assert len(dong_ref) == 3  # 소계 2행 제외
        assert 2611000000 not in dong_ref["행정동코드"].values
        assert 2611051000 in dong_ref["행정동코드"].values
