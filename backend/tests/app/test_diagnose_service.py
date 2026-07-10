import pandas as pd
import pytest

from app.schemas import DiagnoseRequest
from app.services import diagnose_service
from pipeline.layer0_data_contract import profiler


class TestParsingHelpers:
    def test_parse_age_group_takes_lower_bound(self):
        assert diagnose_service.parse_age_group("25-29") == 25.0

    def test_parse_age_group_handles_no_digits(self):
        assert diagnose_service.parse_age_group("모름") is None

    def test_parse_income_band_takes_midpoint(self):
        assert diagnose_service.parse_income_band("2500-3000") == pytest.approx(2750.0)

    def test_parse_income_band_single_number(self):
        assert diagnose_service.parse_income_band("3000") == pytest.approx(3000.0)

    def test_parse_home_ownership_owner(self):
        assert diagnose_service.parse_home_ownership("자가") == 1

    def test_parse_home_ownership_renter(self):
        assert diagnose_service.parse_home_ownership("월세") == 0
        assert diagnose_service.parse_home_ownership("전세") == 0


class TestBuildPopulationReference:
    def test_numeric_column_uses_median(self):
        df = pd.DataFrame({"추정월소득": [100, 200, 300]})
        config = {"columns": {}}
        reference = diagnose_service.build_population_reference(df, config)
        assert reference["추정월소득"] == 200.0

    def test_categorical_column_uses_mode(self):
        df = pd.DataFrame({"성별": [1, 1, 2]})
        config = {"columns": {"성별": {"dtype": "categorical"}}}
        reference = diagnose_service.build_population_reference(df, config)
        assert reference["성별"] == 1


class TestBuildApproximateInputRow:
    def test_known_fields_override_population_reference(self):
        featured_df = pd.DataFrame(
            {
                "연령대": [20, 30, 40],
                "추정월소득": [1000, 2000, 3000],
                "자가거주여부": [0, 1, 0],
                "총대출건수": [0, 2, 3],
                "거주지 시군구 코드": [26260, 26230, 26350],
            }
        )
        config = profiler.load_column_config()
        payload = DiagnoseRequest(
            age_group="25-29", dong_code="26440", income_band="2500-3000", housing_type="자가", has_debt=False
        )
        row = diagnose_service.build_approximate_input_row(payload, featured_df, config)

        assert row.iloc[0]["연령대"] == 25.0
        assert row.iloc[0]["추정월소득"] == pytest.approx(2750.0)
        assert row.iloc[0]["자가거주여부"] == 1
        assert row.iloc[0]["총대출건수"] == 0
        assert row.iloc[0]["거주지 시군구 코드"] == "26440"

    def test_has_debt_true_uses_median_of_positive_debtors(self):
        featured_df = pd.DataFrame({"총대출건수": [0, 0, 2, 4], "연령대": [25, 25, 25, 25]})
        config = profiler.load_column_config()
        payload = DiagnoseRequest(
            age_group="25-29", dong_code="26440", income_band="2000-2500", housing_type="월세", has_debt=True
        )
        row = diagnose_service.build_approximate_input_row(payload, featured_df, config)
        assert row.iloc[0]["총대출건수"] == pytest.approx(3.0)  # median of [2, 4]
